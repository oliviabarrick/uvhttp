from nose.tools import *
from uvhttp.utils import start_loop
import uvhttp.http
import uvhttp.pool
import asyncio
import functools
import time
import hashlib
import ssl
import zlib

def md5(data):
    return hashlib.md5(data).hexdigest()

@start_loop
async def test_http_request(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 80, pool_available, loop)
    conn.locked = True

    assert conn.locked

    request = uvhttp.http.HTTPRequest(conn)
    await request.send(b'HEAD', b'127.0.0.1', b'/')
    assert request.status_code == 200

    assert b"nginx" in request.headers[b"Server"]

    assert not conn.locked

@start_loop
async def test_gzipped_http_request(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 80, pool_available, loop)

    for _ in range(6):
        conn.locked = True

        assert conn.locked

        request = uvhttp.http.HTTPRequest(conn)
        await request.send(b'GET', b'127.0.0.1', b'/index.html', headers={
            b'Accept-Encoding': b'gzip'
        })

        assert request.status_code == 200

        assert b'nginx' in request.headers[b'Server']
        assert b'gzip' in request.headers[b'Content-Encoding']

        assert 'Welcome to nginx' in request.text
        assert 'Welcome to nginx' in request.text
        assert b'Welcome to nginx' in request.text.encode()

        assert not conn.locked

@start_loop
async def test_http_connection_reuse(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 80, pool_available, loop)

    # Send an HTTP request
    conn.locked = True
    assert conn.locked

    request = uvhttp.http.HTTPRequest(conn)
    await request.send(b'HEAD', b'127.0.0.1', b'/')
    assert request.status_code == 200

    assert not conn.locked

    # Send another HTTP request
    conn.locked = True
    assert conn.locked

    request = uvhttp.http.HTTPRequest(conn)
    await request.send(b'GET', b'127.0.0.1', b'/lol')
    assert request.status_code == 404
    assert b'<head><title>404 Not Found</title></head>' in request.content

    assert not conn.locked

    assert conn.connect_count == 1

@start_loop
async def test_session(loop):
    session = uvhttp.http.Session(1, loop)

    for _ in range(5):
        try:
            response = await session.request(b'HEAD', b'http://127.0.0.1/')
            assert response.status_code == 200
        except uvhttp.http.EOFError:
            pass

        try:
            response = await session.request(b'GET', b'http://127.0.0.1/lol')
            assert response.status_code == 404
            assert b'<head><title>404 Not Found</title></head>' in response.content
        except uvhttp.http.EOFError:
            pass

        try:
            response = await session.request(b'GET', b'http://127.0.0.3/', headers={
                b'Host': b'www.google.com'
            })
            assert response.status_code == 302
            assert b"<center><h1>302 Found</h1></center>" in response.content
            assert response.headers[b"Location"] == b"http://www.google.com/test"
        except uvhttp.http.EOFError:
            pass

        try:
            response = await session.request(b'GET', b'http://127.0.0.2/', headers={
                b'Host': b'imgur.com'
            })
            assert response.status_code == 200
            assert len(response.content) > 100000
        except uvhttp.http.EOFError:
            pass

        try:
            response = await session.request(b'GET', b'http://127.0.0.2/', headers={
                b'Host': b'imgur.com',
                b"Accept-Encoding": b"gzip"
            })
            assert response.status_code == 200
            assert len(response.content) > 10000
        except uvhttp.http.EOFError:
            pass

    assert await session.connections() == 3

@start_loop
async def test_session_no_keepalives(loop):
    session = uvhttp.http.Session(1, loop)

    for _ in range(6):
        response = await session.request(b'HEAD', b'http://127.0.0.1/no_keepalive')
        assert response.status_code == 200

    connections = await session.connections()
    assert_equal(connections, 6)

@start_loop
async def test_session_low_keepalives(loop):
    session = uvhttp.http.Session(1, loop)

    for _ in range(6):
        response = await session.request(b'HEAD', b'http://127.0.0.1/low_keepalive')
        assert response.status_code == 200

    connections = await session.connections()
    assert_equal(connections, 3)

@start_loop
async def test_session_benchmark(loop):
    return
    num_requests = 20000

    async def do_request(session):
        response = await session.request(b'HEAD', b'http://127.0.0.1/')
        assert response.status_code == 200

    session = uvhttp.http.Session(10, loop)
    start_time = time.time()

    tasks = []
    for j in range(num_requests):
        task = do_request(session)
        task = asyncio.ensure_future(task)
        tasks.append(task)

    await asyncio.wait(tasks)

    duration = time.time() - start_time
    print('Test time: {}s, {} rps'.format(duration, num_requests / duration))

    assert await session.connections() == 10

@start_loop
async def test_json_body(loop):
    session = uvhttp.http.Session(10, loop)

    response = await session.request(b'GET', b'http://127.0.0.1/test.json')

    assert response.json() == [{"this is a json": "Body!"}]

@start_loop
async def test_text_request_body(loop):
    session = uvhttp.http.Session(10, loop)

    response = await session.post(b'http://127.0.0.1/proxy/echo', data=b'hello')
    assert response.json()["body"] == 'hello'

@start_loop
async def test_request_with_dns(loop):
    session = uvhttp.http.Session(10, loop)

    response = await session.post(b'http://uvhttp/proxy/echo', data=b'hello')
    response_json = response.json()
    assert_equal(response_json["body"], 'hello')
    assert_equal(response_json["headers"]["host"], 'uvhttp')

@start_loop
async def test_request_with_custom_resolver(loop):
    resolver = uvhttp.dns.Resolver(loop)
    resolver.add_to_cache(b'other-site', 80, b'127.0.0.1', 80)

    session = uvhttp.http.Session(10, loop, resolver=resolver)

    response = await session.post(b'http://other-site/proxy/echo', data=b'hello')
    response_json = response.json()
    assert_equal(response_json["body"], 'hello')
    assert_equal(response_json["headers"]["host"], 'other-site')

@start_loop
async def test_request_with_ssl(loop):
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    session = uvhttp.http.Session(10, loop)

    response = await session.post(b'https://uvhttp/proxy/echo', data=b'hello', ssl=ssl_ctx)
    response_json = response.json()
    assert_equal(response_json["body"], 'hello')
    assert_equal(response_json["headers"]["host"], 'uvhttp')

