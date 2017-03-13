#!/usr/bin/env python3
import asyncio
import time

from uvhttp.utils import start_loop, run_workers, NUM_WORKERS
import uvhttp.http

NUM_REQUESTS = 100000

@start_loop
async def main(loop):
    async def request(session):
        response = await session.request(b'HEAD', b'http://127.0.0.1/', headers={
            b'User-Agent': b'fast-af'
        })

        response = await response.body()

    num_requests = int(NUM_REQUESTS / NUM_WORKERS)
    session = uvhttp.http.Session(10, loop)
    tasks = []

    for j in range(num_requests):
        task = request(session)
        task = asyncio.ensure_future(task)
        tasks.append(task)

    await asyncio.wait(tasks)

    connect_count = await session.connections()
    print('Requests per connection: {}'.format(num_requests / connect_count))

if __name__ == '__main__':
    start = time.time()
    run_workers(main)
    total = time.time() - start
    print('%s HTTP requests in %.2f seconds, %.2f rps' % (NUM_REQUESTS, total, NUM_REQUESTS / total))
