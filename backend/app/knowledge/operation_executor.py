"""Serialized execution of knowledge database operations."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import RLock

_executor = None
_lock = RLock()


def get_executor():
    global _executor

    with _lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="voca-knowledge",
            )

        return _executor


async def run_knowledge_operation(function, *args, **kwargs):
    loop = asyncio.get_running_loop()

    operation = partial(function, *args, **kwargs)

    return await loop.run_in_executor(
        get_executor(),
        operation,
    )


def shutdown_knowledge_executor():
    global _executor

    with _lock:
        if _executor is not None:
            _executor.shutdown(wait=True)
            _executor = None
