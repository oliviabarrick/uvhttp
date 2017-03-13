import asyncio
import urllib
import urllib.parse
from httptools import HttpResponseParser, parse_url
from uvhttp import pool

class Session:
    """
    A Session is an HTTP request pool that allows up to request_limit requests
    in flight at once, with up to conn_limit connections per ip/port.
    """
    def __init__(self, conn_limit, loop):
        self.conn_limit = conn_limit
        self.loop = loop

        self.hosts = {}

    async def request(self, method, url, headers=None):
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
        await request.send(method, path, headers)
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

    async def send(self, method, path, headers=None):
        """
        Send the request (usually called by the Session object).
        """
        self.headers_complete = False
        self.done = False
        self.headers = {}
        self.content = b''
        self.status = None
        self.parser = HttpResponseParser(self)

        original_headers = {
            b"Host": b"127.0.0.1",
            b"User-Agent": b"uvloop http client"
        }

        headers = headers or {}
        headers.update(original_headers)

        request = b"\r\n".join(
            [ b" ".join([method, path, b"HTTP/1.1"]) ] +
            [ b": ".join(header) for header in headers.items() ] +
            [ b"\r\n" ]
        )

        await self.connection.send(request)

        await self.fetch_headers()

    async def fetch_headers(self):
        while not self.headers_complete and not self.done:
            data = await self.connection.read(65535)
            if not data:
                self.done = True
            self.parser.feed_data(data)

        self.status = self.parser.get_status_code()

    async def body(self):
        """
        Wait for the response body.
        """
        while not self.done:
            data = await self.connection.read(65535)
            self.parser.feed_data(data)

        self.close()
        return self

    def close(self):
        """
        Closes the request, signalling that we're done with the request. The
        connection is kept open and released back to the pool for re-use.
        """
        self.connection.release()

    def on_header(self, name, value):
        self.headers[name] = value

    def on_body(self, body):
        self.content += body

    def on_headers_complete(self):
        self.headers_complete = True
        self.done = True

    def on_chunk_complete(self):
        self.done = True

    def on_message_complete(self):
        self.done = True

    def on_message_begin(self):
        self.done = False
