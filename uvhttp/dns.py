import aiodns
import asyncio
import random
import socket
import time
import uvhttp.utils

class DNSError(Exception):
    pass

class Resolver:
    """
    Caching DNS resolver wrapper for aiodns.
    """
    def __init__(self, loop, ipv6=True, nameservers=None):
        """
        If ``ipv6`` is true, the resolver will prefer IPv6.
        """
        self.loop = loop
        self.resolver = aiodns.DNSResolver(loop=self.loop, nameservers=nameservers)
        self.cached = {}
        self.ipv6 = ipv6

    def add_to_cache(self, host, host_port, ip, ttl, port=80, overwrite=True):
        """
        Add the address pair ``host`` and ``host_port`` to the DNS cache pointing
        to ``ip`` and ``port``.

        The result will be cached for ``ttl`` (or forever if ``ttl`` is 0).

        If ``overwrite`` is true, the result will overwrite any previous entries,
        otherwise it will be appended.
        """

        addr_pair = (host, host_port)
        if ttl:
            expires = time.time() + ttl
        else:
            expires = 9999999999999

        if overwrite or addr_pair not in self.cached:
            self.cached[addr_pair] = [(ip, port, expires)]
        else:
            self.cached[addr_pair].append((ip, port, expires))

    def fetch_from_cache(self, host, host_port):
        """
        Retrieve the cached entry for the ``host`` and ``host_port`` address
        pair. Returns ``None`` if there are no cached entries.
        """
        addr_pair = (host, host_port)

        if addr_pair not in self.cached:
            return

        self.filter_expired(addr_pair)

        if self.cached[addr_pair]:
            return random.choice(self.cached[addr_pair])

    def filter_expired(self, addr_pair):
        """
        Remove expired entries from a cached address pair.
        """
        now = time.time()
        self.cached[addr_pair] = list(filter(lambda c: c[2] > now, self.cached[addr_pair]))

    async def resolve(self, host, port):
        """
        Resolve ``host`` and ``port`` to its IP and port.
        """
        if uvhttp.utils.is_ip(host):
            return (host, port)

        cached = self.fetch_from_cache(host, port)
        if cached:
            return cached

        if self.ipv6:
            query_types = ['AAAA', 'A']
        else:
            query_types = ['A']

        for query_type in query_types:
            try:
                responses = await self.resolver.query(host, query_type)
            except aiodns.error.DNSError as e:
                pass
            else:
                # sometimes the resolver returns an empty list and I don't know why.
                if not responses:
                    continue

                for response in responses:
                    self.add_to_cache(host, port, response.host, response.ttl, port=port)
                break

        response = self.fetch_from_cache(host, port)
        if not response:
            raise DNSError()
        else:
            return response
