import asyncio
import json
import urllib
import urllib.parse
import zlib
from httptools import HttpResponseParser, parse_url
from uvhttp import pool
from uvhttp.utils import HeaderDict

class EOFError(Exception):
    pass

class Session:
    """
    A Session is an HTTP request pool that allows up to request_limit requests
    in flight at once, with up to conn_limit connections per ip/port::

        from uvhttp.utils import start_loop
        import uvhttp.http

        NUM_CONNS_PER_HOST = 10

        @start_loop
        async def main(loop):
            session = uvhttp.http.Session(NUM_CONNS_PER_HOST, loop)

            for _ in range(6):
            response = await session.get(b'http://www.google.com/', headers={
                b'User-Agent': b'fast-af'
            })

            print(response.text)

        if __name__ == '__main__':
            main()

    The module is designed to send HTTP requests very quickly, so all methods
    require ``bytes`` objects instead of strings.
    """
    def __init__(self, conn_limit, loop, resolver=None):
        self.conn_limit = conn_limit
        self.loop = loop
        self.resolver = resolver

        self.hosts = {}

    async def head(self, *args, **kwargs):
        """
        Make an HTTP HEAD request to url, see :meth:`.head`.
        """
        return await self.request(b'HEAD', *args, **kwargs)

    async def get(self, *args, **kwargs):
        """
        Make an HTTP GET request to url, see :meth:`.request`.
        """
        return await self.request(b'GET', *args, **kwargs)

    async def post(self, *args, **kwargs):
        """
        Make an HTTP POST request to url, see :meth:`.request`.
        """
        return await self.request(b'POST', *args, **kwargs)

    async def put(self, *args, **kwargs):
        """
        Make an HTTP PUT request to url, see :meth:`.request`.
        """
        return await self.request(b'PUT', *args, **kwargs)

    async def delete(self, *args, **kwargs):
        """
        Make an HTTP DELETE request to url, see :meth:`.request`.
        """
        return await self.request(b'DELETE', *args, **kwargs)

    async def request(self, method, url, headers=None, data=None, ssl=None):
        """
        Make a new HTTP request in the pool.

        ``headers`` can be passed as a dictionary of :class:`byte` (not :class:`str`).

        ``data`` is a byte array of data to include in the request.

        ``ssl`` can be a :class:`ssl.SSLContext` or True and must match
        the schema in the URL.
        """

        # Parse the URL for the hostname, port, and query string.
        parsed_url = parse_url(url)

        use_ssl = parsed_url.schema == b'https'
        if not use_ssl:
            ssl = None
        else:
            ssl = ssl or True

        port = parsed_url.port
        if not port:
            port = 443 if use_ssl else 80

        host = parsed_url.host

        path = parsed_url.path
        if parsed_url.query:
            path += b'?' + parsed_url.query

        # Find or create a pool for this host/port/scheme combination.
        addr = parsed_url.schema + b':' + host + b':' + str(port).encode()

        session = self.hosts.get(addr)
        if not session:
            session = pool.Pool(host, port, self.conn_limit, self.loop, resolver=self.resolver, ssl=ssl)
            self.hosts[addr] = session

        # Create and send the new HTTP request.
        request = HTTPRequest(await session.connect())
        await request.send(method, host, path, headers, data)
        return request

    async def connections(self):
        connections = 0

        for host, pool in self.hosts.items():
            connections += await pool.stats()

        return connections

class HTTPRequest:
    """
    An HTTP request instantiated from a :class:`.Session`. HTTP requests are returned by the HTTP
    session once they are sent and contain all information about the request and response.
    """
    def __init__(self, connection):
        self.connection = connection

    async def send(self, method, host, path, headers=None, data=None):
        """
        Send the request (usually called by the Session object).
        """
        self.__keep_alive = None
        self.__gzipped = None

        self.headers_complete = False
        self.contains_body = False
        self.body_done = True

        self.__text = b''
        self.content = b''
        self.__headers = {}
        self.__header_dict = None
        self.parser = HttpResponseParser(self)

        self.method = method

        self.request_headers = {
            b"Host": host,
            b"User-Agent": b"uvloop http client"
        }

        if data:
            self.request_headers[b"Content-Length"] = str(len(data)).encode()

        if headers:
            self.request_headers.update(headers)

        request = b"\r\n".join(
            [ b" ".join([method, path, b"HTTP/1.1"]) ] +
            [ b": ".join(header) for header in self.request_headers.items() ] +
            [ b"\r\n" ]
        )

        if data:
            request += data

        await self.connection.send(request)

        try:
            await self.fetch()
        except EOFError as e:
            if self.headers[b'transfer-encoding'] \
              or self.headers[b'content-encoding'] or self.headers[b'content-length']:
                raise e

        self.status_code = self.parser.get_status_code()

    async def fetch(self):
        # TODO: support streaming
        while not self.headers_complete or not self.body_done:
            data = await self.connection.read(65535)

            if not data:
                self.close()
                raise EOFError()

            self.parser.feed_data(data)

        self.close()

    def close(self):
        """
        Closes the request, signalling that we're done with the request. The
        connection is kept open and released back to the pool for re-use.
        """
        if not self.keep_alive:
            self.connection.close()

        self.connection.release()

    @property
    def keep_alive(self):
        if self.__keep_alive == None:
            connection = self.headers[b'connection']
            self.__keep_alive = not connection or connection != b'close'

        return self.__keep_alive

    @property
    def gzipped(self):
        """
        Return true if the response is gzipped.
        """
        if self.__gzipped == None:
            encoding = self.headers[b'content-encoding'] + self.headers[b'transfer-encoding']
            self.__gzipped = b'gzip' in encoding or b'deflate' in encoding

        return self.__gzipped

    def json(self):
        """
        Return the JSON decoded version of the body.
        """
        # TODO: Possibly should use a better library.
        return json.loads(self.text)

    @property
    def text(self):
        """
        The string representation of the response body. It will be ungzipped
        and encoded as a unicode string.
        """
        if self.__text:
            return self.__text

        if self.gzipped:
            self.__text = zlib.decompress(self.content, 16 + zlib.MAX_WBITS)
        else:
            self.__text = self.content

        self.__text = self.__text.decode('utf-8')
        return self.__text

    @property
    def headers(self):
        """
        Return the headers from the request in a case-insensitive dictionary.
        """
        if self.headers_complete and self.__header_dict:
            return self.__header_dict

        self.__header_dict = HeaderDict(self.__headers)
        return self.__header_dict

    def on_header(self, name, value):

        self.__headers[name] = value

    def on_body(self, body):
        self.content += body

    def on_headers_complete(self):
        self.headers_complete = True

    def on_chunk_complete(self):
        self.body_done = True

    def on_message_complete(self):
        self.body_done = True

    def on_message_begin(self):
        if self.method != b"HEAD":
            self.body_done = False
