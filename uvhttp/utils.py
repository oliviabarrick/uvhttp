import asyncio
import functools
import multiprocessing
import os
import socket
import ssl
from json import loads
from sanic import Sanic
from sanic.response import json

NUM_WORKERS = int(os.getenv("GOMAXPROCS", multiprocessing.cpu_count() * 2))

def start_loop(func):
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(func(loop))

    return new_func

def run_workers(func):
    procs = []

    if NUM_WORKERS > 1:
        for _ in range(NUM_WORKERS):
            proc = multiprocessing.Process(target=func)
            proc.start()
            procs.append(proc)

        for proc in procs:
            proc.join()
    else:
        func()

def is_ip(host):
    """
    Return True if ``host`` is an IPv4 or IPv6 address.
    """
    if isinstance(host, bytes):
        host = host.decode()

    try:
        socket.inet_pton(socket.AF_INET, host)
        return True
    except socket.error:
        pass

    try:
        socket.inet_pton(socket.AF_INET6, host)
        return True
    except socket.error:
        return False

class HeaderDict:
    def __init__(self, original):
        self.__dict = dict([ (k.upper(), (k, v)) for k, v in original.items() ])

    def __getitem__(self, key):
        try:
            return self.__dict[key.upper()][1]
        except KeyError:
            return b''

    def __iter__(self):
        for value in self.__dict.values():
            yield value[0]

    def keys(self):
        return [ key for key in self ]

    def items(self):
        for key, value in self.__dict.items:
            yield value

class HttpServer:
    """
    An HTTP server that uses Sanic in the backend to help write unit
    tests.
    """
    def __init__(self, host=None, port=None, https_host=None, https_port=None):
        self.app = Sanic(__name__)
        self.app.config.LOGO = None

        self.host = host or '127.0.0.1'
        self.port = port or 8089
        self.https_host = https_host or '127.0.0.1'
        self.https_port = https_port or 8090

        self.add_routes()

    @property
    def url(self):
        """
        Return the URL of the started server.
        """
        return 'http://{}:{}/'.format(self.host, self.port).encode()

    @property
    def https_url(self):
        """
        Return the HTTPS URL of the started server.
        """
        return 'https://{}:{}/'.format(self.https_host, self.https_port).encode()

    async def start(self):
        """
        Start the server.
        """
        self.server = await self.app.create_server(host=self.host, port=self.port)

        pem = os.path.join(os.path.dirname(__file__), 'example.pem')

        ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        ctx.load_cert_chain(pem)

        self.https_server = await self.app.create_server(host=self.https_host, port=self.https_port, ssl=ctx)

    def stop(self):
        """
        Stop the server
        """
        self.server.close()
        self.https_server.close()

    def add_routes(self):
        """
        A function for adding all of the routes you need. Implement
        this in your inherited class to add your endpoints.
        """
        self.app.add_route(self.echo, "echo", [ 'GET', 'POST' ])

    async def echo(self, request):
        """
        An echo endpoint that returns all of the data about the request.
        """
        try:
            parsed_json = loads(request.body)
        except (ValueError, TypeError):
            parsed_json = None

        return json({
            "form": request.form,
            "body": request.body,
            "args": request.args,
            "url": request.url,
            "query": request.query_string,
            "json": parsed_json,
            "headers": request.headers
        })

def http_server(http_server_cls, *server_args, **server_kwargs):
    """
    Start a :class:`.HttpServer` and an event loop for use in a test case.
    """
    def http_server_wrapper(func):
        @functools.wraps(func)
        @start_loop
        async def real_http_server_wrapper(loop, *args, **kwargs):
            server = http_server_cls(*server_args, **server_kwargs)
            await server.start()

            try:
                await func(server, loop, *args, **kwargs)
            finally:
                server.stop()

        return real_http_server_wrapper

    return http_server_wrapper

def http_server_no_loop(http_server_cls, *server_args, **server_kwargs):
    """
    Start a :class:`.HttpServer` for use in a test case.
    """
    def http_server_wrapper(func):
        @functools.wraps(func)
        async def real_http_server_wrapper(*args, **kwargs):
            server = http_server_cls(*server_args, **server_kwargs)
            await server.start()

            try:
                await func(server, *args, **kwargs)
            finally:
                server.stop()

        return real_http_server_wrapper

    return http_server_wrapper
