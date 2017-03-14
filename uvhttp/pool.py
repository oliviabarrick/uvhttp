import asyncio
import uvloop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

class Connection:
    """
    A single connection within a pool. When the acquire() method is called,
    the connection is locked until release() is called, when it will be
    released back into the pool.
    """
    def __init__(self, host, port, pool_available, loop):
        self.loop = loop

        # Semaphore used by the Pool to determine if any connections are
        # available.
        self.pool_available = pool_available

        # Lock used to lock the connection, is released by release() to release
        # the connection back into the pool. Note that this is just a boolean
        # since a lock is not needed due to the way this variable is accessed.
        self.locked = False

        self.reader = None
        self.writer = None

        self.host = host
        self.port = port

        # Number of reconnects made. Used to determine pool efficiency.
        self.connect_count = 0

    async def connect(self):
        """
        Open a new connection to the server. Should only be called when the
        connection has not established yet or we disconnected.
        """
        self.connect_count += 1
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port, loop=self.loop)

    async def read(self, num_bytes):
        """
        Read up to num_bytes off of the socket.
        """
        if not self.reader:
            await self.connect()

        data = await self.reader.read(num_bytes)
        if not data:
            self.close()

        return data

    async def send(self, message):
        """
        Write up to num_bytes off of the socket.
        """
        if not self.writer:
            await self.connect()

        self.writer.write(message)

    def release(self):
        """
        Called once the connection is no longer needed to release back into
        the pool.
        """
        self.locked = False
        self.pool_available.release()

    def close(self):
        """
        Close a connection (will trigger a reconnect next time the Connection)
        is retrieved from the pool and used.
        """
        if self.writer:
            self.writer.close()
        self.writer = None
        self.reader = None

class Pool:
    """
    A connection pool for a single host and port. It allows up to conn_limit
    connections to a single host at once.
    """
    def __init__(self, host, port, conn_limit, loop):
        self.conn_limit = conn_limit

        self.host = host
        self.port = port

        self.loop = loop

        self.pool = []
        self.pool_available = asyncio.Semaphore(self.conn_limit, loop=loop)
        self.pool_lock = asyncio.Lock(loop=loop)

    async def connect(self):
        """
        Waits for an available connection and then returns a connection object
        ready to use.
        """
        await self.pool_available.acquire()

        c = None

        if len(self.pool) < self.conn_limit:
            c = Connection(self.host, self.port, self.pool_available, self.loop)
            c.locked = True
            self.pool.append(c)
        else:
            for i, connection in enumerate(self.pool):
                if not connection.locked:
                    connection.locked = True
                    c = connection
                    break

        return c

    async def stats(self):
        """
        Count how many times each Connection object reconnected to determine
        pool efficiency.
        """
        connections = 0

        async with self.pool_lock:
            for connection in self.pool:
                connections += connection.connect_count

        return connections
