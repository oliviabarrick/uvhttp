[uvloop-based](https://github.com/magicstack/uvloop) high performance HTTP client.

See their [blog](https://magic.io/blog/uvloop-blazing-fast-python-networking/) for details.

# Benchmarks

All benchmarks running with 8 cores, see [bencher](https://codesink.net/justin/bencher).

uvhttp benchmark:

```
➜  uvhttp git:(master) ✗ ./uvhttp.py
100000 HTTP requests in 3.63 seconds, 27564.66 rps
➜  uvhttp git:(master) ✗
```

asyncio with aiohttp:

```
➜  bencher git:(master) ✗ python3 http_test_asyncio_aiohttp.py
10000 HTTP requests in 1.67 seconds, 5991.36 rps
➜  bencher git:(master) ✗
```

uvloop with aiohttp is still not great:

```
➜  bencher git:(master) ✗ python3 http_test_uvloop_aiohttp.py
10000 HTTP requests in 1.97 seconds, 5065.03 rps
➜  bencher git:(master) ✗
```

gevent is even worse:

```
➜  bencher git:(master) ✗ python3 http_test_gevent.py 
10000 HTTP requests in 6.93 seconds, 1443.02 rps
➜  bencher git:(master) ✗ 
```

We are striving for go performance:

```
http_test.go:53: 100000 HTTP requests in 2.274069869 seconds, 43974.02268206211 rps
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

        print(response.status)

if __name__ == '__main__':
    main()
```
