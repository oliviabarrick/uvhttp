[uvloop-based](https://github.com/magicstack/uvloop) high performance HTTP client.

See their [blog](https://magic.io/blog/uvloop-blazing-fast-python-networking/) for details.

# Benchmarks

All benchmarks running with 8 cores, see [bencher](https://codesink.net/justin/bencher).

uvhttp benchmark:

```
➜  uvhttp git:(master) ✗ ./uvhttp.py
100000 HTTP requests in 4.53 seconds, 22088.08 rps
➜  uvhttp git:(master) ✗
```

asyncio with aiohttp:

```
➜  bencher git:(master) ✗ python3 http_test_asyncio_aiohttp.py
10000 HTTP requests in 2.43 seconds, 4109.63 rps
➜  bencher git:(master) ✗
```

uvloop with aiohttp is still not great:

```
➜  bencher git:(master) ✗ python3 http_test_uvloop_aiohttp.py
10000 HTTP requests in 2.23 seconds, 4480.41 rps
➜  bencher git:(master) ✗
```

gevent is even worse:

```
➜  bencher git:(master) ✗ python3 http_test_gevent.py 
10000 HTTP requests in 7.81 seconds, 1281.19 rps
➜  bencher git:(master) ✗ 
```

We are striving for go performance:

```
http_test.go:53: 100000 HTTP requests in 3.225065352 seconds, 31007.12360386302 rps
```

# Installation

To install:

```
git clone https://codesink.net/justin/uvhttp.git
cd uvhttp/
pip3 install --user -r requirements.txt
```

# Usage

Usage will eventually be requests-like:

```
from uvhttp.utils import start_loop
import uvhttp.http

NUM_REQUESTS = 1000
NUM_CONNS_PER_HOST = 10

@start_loop
async def main(loop):
    session = uvhttp.http.Session(NUM_REQUESTS, NUM_CONNS_PER_HOST, loop)

    for _ in range(6):
        response = await session.request('HEAD', 'http://127.0.0.1/', headers={
            'User-Agent': 'fast-af'
        })

        response = await response.body()

if __name__ == '__main__':
    main()
```
