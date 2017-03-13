import asyncio
import functools
import multiprocessing
import os

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
