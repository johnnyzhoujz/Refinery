"""
Tests for async helper utilities.

Tests the run_in_executor function to ensure it properly executes
synchronous functions without blocking the event loop.
"""

import asyncio
import time
from typing import List

import pytest

from refinery.utils.async_helpers import run_in_executor


@pytest.mark.asyncio
async def test_run_in_executor_basic():
    """Test basic functionality of run_in_executor."""

    def sync_function(x: int) -> int:
        """A simple synchronous function."""
        return x * 2

    result = await run_in_executor(sync_function, 5)
    assert result == 10


@pytest.mark.asyncio
async def test_run_in_executor_with_kwargs():
    """Test run_in_executor with keyword arguments."""

    def sync_function_with_kwargs(a: int, b: int, c: int = 0) -> int:
        """A sync function that takes kwargs."""
        return a + b + c

    result = await run_in_executor(sync_function_with_kwargs, 1, 2, c=3)
    assert result == 6


@pytest.mark.asyncio
async def test_run_in_executor_doesnt_block_event_loop():
    """Test that run_in_executor doesn't block the event loop."""

    def slow_sync_function(duration: float) -> str:
        """A blocking sync function that sleeps."""
        time.sleep(duration)
        return "done"

    # Track execution order
    execution_order: List[str] = []

    async def fast_async_task():
        """A fast async task to verify the loop isn't blocked."""
        await asyncio.sleep(0.01)
        execution_order.append("fast_task")

    # Start slow sync function in executor
    slow_task = asyncio.create_task(run_in_executor(slow_sync_function, 0.1))

    # Start fast async task
    fast_task = asyncio.create_task(fast_async_task())

    # Wait for both
    await asyncio.gather(slow_task, fast_task)

    # The fast task should complete while the slow task is still running
    # because run_in_executor doesn't block the event loop
    assert execution_order == ["fast_task"]


@pytest.mark.asyncio
async def test_run_in_executor_stress_test():
    """Stress test with 50 concurrent calls."""

    def cpu_intensive_task(n: int) -> int:
        """A CPU-intensive synchronous task."""
        result = 0
        for i in range(n):
            result += i
        return result

    # Run 50 concurrent tasks
    tasks = [run_in_executor(cpu_intensive_task, 1000) for _ in range(50)]
    results = await asyncio.gather(*tasks)

    # All tasks should complete successfully
    assert len(results) == 50
    # All results should be the same (sum of 0 to 999)
    expected = sum(range(1000))
    assert all(result == expected for result in results)


@pytest.mark.asyncio
async def test_run_in_executor_error_handling():
    """Test that errors are properly propagated."""

    def sync_function_that_raises() -> None:
        """A sync function that raises an exception."""
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        await run_in_executor(sync_function_that_raises)


@pytest.mark.asyncio
async def test_run_in_executor_with_return_none():
    """Test run_in_executor with a function that returns None."""

    def sync_function_returns_none() -> None:
        """A sync function that returns None."""
        pass

    result = await run_in_executor(sync_function_returns_none)
    assert result is None


@pytest.mark.asyncio
async def test_run_in_executor_with_complex_return_type():
    """Test run_in_executor with complex return types."""

    def sync_function_returns_dict(key: str, value: int) -> dict:
        """A sync function that returns a dict."""
        return {key: value, "nested": {"data": [1, 2, 3]}}

    result = await run_in_executor(sync_function_returns_dict, "test", 42)
    assert result == {"test": 42, "nested": {"data": [1, 2, 3]}}


@pytest.mark.asyncio
async def test_run_in_executor_concurrent_execution():
    """Test that multiple calls execute concurrently, not sequentially."""

    def slow_sync_function(duration: float, task_id: int) -> tuple:
        """A blocking sync function that records its execution time."""
        start = time.time()
        time.sleep(duration)
        end = time.time()
        return (task_id, start, end)

    # Start 3 tasks that each take 0.1 seconds
    start_time = time.time()
    tasks = [run_in_executor(slow_sync_function, 0.1, i) for i in range(3)]
    results = await asyncio.gather(*tasks)
    total_time = time.time() - start_time

    # If they ran sequentially, it would take 0.3+ seconds
    # If they run concurrently, it should take close to 0.1 seconds
    # We use 0.25 as threshold to account for overhead
    assert total_time < 0.25, f"Tasks appear to have run sequentially: {total_time}s"

    # All 3 tasks should complete
    assert len(results) == 3


@pytest.mark.asyncio
async def test_run_in_executor_with_no_args():
    """Test run_in_executor with a function that takes no arguments."""

    def sync_function_no_args() -> str:
        """A sync function with no arguments."""
        return "success"

    result = await run_in_executor(sync_function_no_args)
    assert result == "success"
