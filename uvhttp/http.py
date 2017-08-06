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
    in flight at once, with up to conn_limit connections per ip/port.
    """
    def __init__(self, conn_limit, loop):
        self.conn_limit = conn_limit
        self.loop = loop

        self.hosts = {}

    async def head(self, url, headers=None, data=None):
        return await self.request(b'HEAD', url, headers, data)

    async def get(self, url, headers=None, data=None):
        return await self.request(b'GET', url, headers, data)

    async def post(self, url, headers=None, data=None):
        return await self.request(b'POST', url, headers, data)

    async def put(self, url, headers=None, data=None):
        return await self.request(b'PUT', url, headers, data)

    async def delete(self, url, headers=None, data=None):
        return await self.request(b'DELETE', url, headers, data)

    async def request(self, method, url, headers=None, data=None):
        """
        Make a new HTTP request in the pool.
        """

        # Parse the URL for the hostname, port, and query string.
        parsed_url = parse_url(url)

        port = parsed_url.port
        if not port:
            port = 443 if parsed_url.schema == b'https' else 80

        host = parsed_url.host

        path = parsed_url.path
        if parsed_url.query:
            path += b'?' + parsed_url.query

        # Find or create a pool for this host/port/scheme combination.
        addr = parsed_url.schema + b':' + host + b':' + str(port).encode()

        session = self.hosts.get(addr)
        if not session:
            session = pool.Pool(host, port, self.conn_limit, self.loop)
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
    An HTTP request instantiated from a Session.
    """
    def __init__(self, connection):
        self.connection = connection

    async def send(self, method, host, path, headers=None, data=None):
        """
        Send the request (usually called by the Session object).
        """
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

        await self.fetch()

    async def fetch(self):
        # TODO: support streaming
        while not self.headers_complete or not self.body_done:
            data = await self.connection.read(65535)

            if not data:
                self.close()
                raise EOFError()

            self.parser.feed_data(data)

        self.close()

        self.status_code = self.parser.get_status_code()

    def close(self):
        """
        Closes the request, signalling that we're done with the request. The
        connection is kept open and released back to the pool for re-use.
        """
        self.connection.release()

    def gzipped(self):
        encoding = self.headers[b'content-encoding'] + self.headers[b'transfer-encoding']
        return b'gzip' in encoding or b'deflate' in encoding

    def json(self):
        # TODO: Possibly should use a better library.
        return json.loads(self.text)

    @property
    def text(self):
        if self.__text:
            return self.__text

        if self.gzipped():
            self.__text = zlib.decompress(self.content, 16 + zlib.MAX_WBITS)
        else:
            self.__text = self.content

        self.__text = self.__text.decode('utf-8')
        return self.__text

    @property
    def headers(self):
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
