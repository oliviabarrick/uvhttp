from uvhttp.utils import start_loop
import uvhttp.dns
from nose.tools import *
import socket

@start_loop
async def test_caching(loop):
    resolver = uvhttp.dns.Resolver(loop)
    cached = resolver.fetch_from_cache('test', 80)
    assert_equal(cached, None)

    resolver.add_to_cache('test', 80, '127.0.0.1', 40)

    cached = resolver.fetch_from_cache('test', 80)
    assert_equal(cached[:2], ('127.0.0.1', 80))

@start_loop
async def test_cache_expiry(loop):
    resolver = uvhttp.dns.Resolver(loop)

    resolver.add_to_cache('test', 80, '127.0.0.1', -1)

    cached = resolver.fetch_from_cache('test', 80)
    assert_equal(cached, None)

@start_loop
async def test_cache_some_expired(loop):
    resolver = uvhttp.dns.Resolver(loop)

    resolver.add_to_cache('test', 80, '127.0.0.1', -1)
    resolver.add_to_cache('test', 80, '127.0.0.2', 40, port=443)

    cached = resolver.fetch_from_cache('test', 80)
    assert_equal(cached[:2], ('127.0.0.2', 443))

@start_loop
async def test_resolve_from_cache(loop):
    resolver = uvhttp.dns.Resolver(loop)

    resolver.add_to_cache('test', 80, '127.0.0.1', 40)

    result = await resolver.resolve('test', 80)

    assert_equal(result[:2], ('127.0.0.1', 80))

@start_loop
async def test_resolve_failure(loop):
    resolver = uvhttp.dns.Resolver(loop)

    try:
        result = await resolver.resolve('baddns', 80)
    except uvhttp.dns.DNSError:
        return
    else:
        raise AssertionError('DNS resolution should have failed!')

def parse_resolv_conf():
    resolvers = []
    for line in open('/etc/resolv.conf').read().split('\n'):
        if not line or not line.startswith('nameserver'):
            continue
        resolvers.append(line.split()[1])
    return resolvers

@start_loop
async def test_resolve(loop):
    resolvers = parse_resolv_conf()

    uvhttp_addr = socket.gethostbyname('uvhttp')

    resolver = uvhttp.dns.Resolver(loop, nameservers=[resolvers[0]])

    result = await resolver.resolve('uvhttp', 80)

    assert_equal(result[:2], (uvhttp_addr, 80))

@start_loop
async def test_resolve_https(loop):
    resolvers = parse_resolv_conf()

    uvhttp_addr = socket.gethostbyname('uvhttp')

    resolver = uvhttp.dns.Resolver(loop, nameservers=[resolvers[0]])

    result = await resolver.resolve('uvhttp', 443)

    assert_equal(result[:2], (uvhttp_addr, 443))
