import uvhttp.utils
import ssl
from nose.tools import *

def test_is_ip():
    assert_equal(uvhttp.utils.is_ip('127.0.0.1'), True)
    assert_equal(uvhttp.utils.is_ip('::1'), True)
    assert_equal(uvhttp.utils.is_ip('example'), False)
    assert_equal(uvhttp.utils.is_ip('256.0.0.0'), False)

@uvhttp.utils.http_server(uvhttp.utils.HttpServer)
async def test_test_server(server, loop):
    session = uvhttp.http.Session(10, loop)

    response = await session.get(server.url + b'echo')
    assert_equal(response.json()['url'], 'http://127.0.0.1/echo')

@uvhttp.utils.http_server(uvhttp.utils.HttpServer)
async def test_test_https_server(server, loop):
    session = uvhttp.http.Session(10, loop)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    response = await session.get(server.https_url + b'echo', ssl=ctx)
    assert_equal(response.json()['url'], 'https://127.0.0.1/echo')
