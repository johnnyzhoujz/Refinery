"""
Async helper utilities for wrapping synchronous SDK calls.

Provides utilities for safely running synchronous functions in an async context
without blocking the event loop.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Thread pool executor for running sync functions
_executor = ThreadPoolExecutor(max_workers=10)


async def run_in_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Run sync function in thread pool executor.

    This function allows you to run blocking synchronous functions in an async
    context without blocking the event loop. It wraps the function call in a
    lambda and executes it in a thread pool executor.

    Args:
        func: The synchronous function to execute
        *args: Positional arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        The return value of the function

    Raises:
        Any exception raised by the function will be propagated

    Example:
        >>> import time
        >>> def slow_function(x):
        ...     time.sleep(1)
        ...     return x * 2
        >>> result = await run_in_executor(slow_function, 5)
        >>> print(result)
        10
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))
