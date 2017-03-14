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

class HeaderDict:
    def __init__(self, original):
        self.__dict = dict([ (k.upper(), (k, v)) for k, v in original.items() ])

    def __getitem__(self, key):
        try:
            return self.__dict[key.upper()][1]
        except KeyError:
            return b''

    def __iter__(self):
        for value in self.__dict.values():
            yield value[0]

    def keys(self):
        return [ key for key in self ]

    def items(self):
        for key, value in self.__dict.items:
            yield value
