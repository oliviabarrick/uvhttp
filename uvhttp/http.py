import asyncio
import urllib
import urllib.parse
import httptools
from uvhttp import pool

class Session:
    """
    A Session is an HTTP request pool that allows up to request_limit requests
    in flight at once, with up to conn_limit connections per ip/port.
    """
    def __init__(self, request_limit, conn_limit, loop):
        self.request_lock = asyncio.Semaphore(value=request_limit, loop=loop)
        self.conn_limit = conn_limit
        self.loop = loop

        self.hosts = {}

    async def request(self, method, url, headers=None):
        """
        Make a new HTTP request in the pool.
        """

        # Wait for an available request slot to be available (to ensure we
        # never exceed request_limit requests).
        await self.request_lock.acquire()

        # Parse the URL for the hostname, port, and query string.
        parsed_url = httptools.parse_url(url.encode())

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
        request = HTTPRequest(await session.connect(), self.request_lock)
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
    def __init__(self, connection, request_lock):
        self.connection = connection
        self.request_lock = request_lock

    async def send(self, method, path, headers=None):
        """
        Send the request (usually called by the Session object).
        """
        original_headers = {
            "Host": "127.0.0.1",
            "User-Agent": "uvloop http client"
        }

        headers = headers or {}
        headers.update(original_headers)

        request = "{} {} HTTP/1.1\r\n".format(method.upper(), path.decode())
        for header, value in headers.items():
            request += "{}: {}\r\n".format(header, value)
        request += "\r\n"

        await self.connection.send(request)

    async def body(self):
        """
        Wait for the response body.
        """
        data = await self.connection.read(65535)
        self.close()
        return data

    def close(self):
        """
        Closes the request, signalling that we're done with the request. The
        connection is kept open and released back to the pool for re-use.
        """
        self.connection.release()
        self.request_lock.release()
