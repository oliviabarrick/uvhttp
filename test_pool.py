import uvhttp.pool
import asyncio
import functools
import time

HEAD = 'HEAD / HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n'
HEAD_LOW = 'HEAD /low_keepalive HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n'
GET_404 = 'GET /lol HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n'
STATUS_404 = b'HTTP/1.1 404 Not Found'
STATUS_200 = b'HTTP/1.1 200 OK'

def start_loop(func):
    @functools.wraps(func)
    def new_func(*args, **kwargs):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(func(loop))

    return new_func

@start_loop
async def test_connection(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 80, pool_available, loop)

    await conn.acquire()

    await conn.send(HEAD)
    response = await conn.read(65535)
    assert response[:len(STATUS_200)] == STATUS_200

    conn.close()
    conn.release()

@start_loop
async def test_connection_failed(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 31337, pool_available, loop)

    await conn.acquire()

    try:
        await conn.send(HEAD)
        raise AssertionError("ConnectionRefusedError was not raised.")
    except ConnectionRefusedError:
        pass

    conn.close()
    conn.release()

@start_loop
async def test_connection_reuse(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 80, pool_available, loop)
    
    assert not conn.locked()
    await conn.acquire()
    assert conn.locked()

    await conn.send(HEAD)
    response = await conn.read(65535)
    assert response[:len(STATUS_200)] == STATUS_200

    conn.release()
    assert not conn.locked()
    await conn.acquire()

    await conn.send(GET_404)
    response = await conn.read(65535)
    assert response[:len(STATUS_404)] == STATUS_404
    assert b'</html>' in response

    conn.release()
    assert not conn.locked()
    await conn.acquire()

    await conn.send(HEAD)
    response = await conn.read(65535)
    assert response[:len(STATUS_200)] == STATUS_200

    conn.close()
    conn.release()

    assert conn.connect_count == 1

@start_loop
async def test_connection_eof(loop):
    pool_available = asyncio.Semaphore(1, loop=loop)

    conn = uvhttp.pool.Connection('127.0.0.1', 80, pool_available, loop)

    for _ in range(6):
        await conn.acquire()

        await conn.send(HEAD_LOW)
        response = await conn.read(65535)
        if response:
            assert response[:len(STATUS_200)] == STATUS_200
        conn.release()

    assert conn.connect_count == 2

@start_loop
async def test_pool(loop):
    pool = uvhttp.pool.Pool('127.0.0.1', 80, 2, loop)

    # Open two connections in the pool.
    conn = await pool.connect()
    conn2 = await pool.connect()

    # Make sure no connections have actually been established yet.
    assert await pool.stats() == 0

    # Send a request and confirm the response.
    await conn.send(HEAD)
    response = await conn.read(65535)
    assert response[:len(STATUS_200)] == STATUS_200

    # Make sure only one connection has been established so far.
    assert await pool.stats() == 1

    # Send a request on the other connection.
    await conn2.send(GET_404)
    response = await conn2.read(65535)
    assert response[:len(STATUS_404)] == STATUS_404

    # The pool should have two connections now.
    assert await pool.stats() == 2

    # Release the connections to the pool.
    conn.release()
    conn2.release()

    # Retrieve an old connection from the pool.
    conn = await pool.connect()

    await conn.send(HEAD)
    response = await conn.read(65535)
    assert response[:len(STATUS_200)] == STATUS_200

    assert await pool.stats() == 2

    conn.release()

@start_loop
async def test_pool_blocks_when_full(loop):
    pool = uvhttp.pool.Pool('127.0.0.1', 80, 2, loop)

    # Open two connections in the pool.
    conn = await pool.connect()
    conn2 = await pool.connect()

    # Make sure no connections have actually been established yet.
    assert await pool.stats() == 0

    # Send a request and confirm the response.
    await conn.send(HEAD)
    response = await conn.read(65535)
    assert response[:len(STATUS_200)] == STATUS_200

    # Make sure only one connection has been established so far.
    assert await pool.stats() == 1

    # Send a request on the other connection.
    await conn2.send(GET_404)
    response = await conn2.read(65535)
    assert response[:len(STATUS_404)] == STATUS_404

    async def block_this(pool):
        # Make sure it takes 1 second for the pool to be available.
        start_time = time.time()
        conn = await pool.connect()

        # Let the main thread know it should try connecting.
        assert int(time.time() - start_time) == 1

        # Make a request, sleep two seconds, and release the connection for
        # reuse.
        await conn.send(GET_404)
        #response = await conn.read(65535)
        #assert response[:len(STATUS_404)] == STATUS_404
        await asyncio.sleep(2)

        conn.release()

    result = asyncio.Event(loop=loop)

    def blocked_cb(future):
        result.set()

    # Launch a coroutine in the background that is trying to use the pool.
    blocked = asyncio.ensure_future(block_this(pool), loop=loop)
    blocked.add_done_callback(blocked_cb)

    # Don't release the pool for one second.
    await asyncio.sleep(1)
    conn.release()

    await result.wait()
    blocked.result()

    assert await pool.stats() == 2

@start_loop
async def test_pool_benchmark(loop):
    num_requests = 20000

    async def do_request(pool):
        conn = await pool.connect()

        await conn.send(HEAD)
        response = await conn.read(65535)
        assert response[:len(STATUS_200)] == STATUS_200

        conn.release()

    pool = uvhttp.pool.Pool('127.0.0.1', 80, 10, loop)
    start_time = time.time()

    tasks = []
    for j in range(num_requests):
        task = do_request(pool)
        task = asyncio.ensure_future(task)
        tasks.append(task)

    await asyncio.wait(tasks)

    duration = time.time() - start_time
    print('Test time: {}s, {} rps'.format(duration, num_requests / duration))

    assert await pool.stats() == 10
