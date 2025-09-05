import asyncio

import pytest

from marimo._pyodide.restartable_task import RestartableTask


async def test_restartable_task():
    # Test basic start/stop
    counter = 0
    event = asyncio.Event()

    async def increment_counter():
        nonlocal counter
        counter += 1
        event.set()  # Signal that we've incremented
        await asyncio.sleep(0.1)

    task = RestartableTask(increment_counter)
    assert counter == 0

    # Start task
    start_task = asyncio.create_task(task.start())
    await event.wait()  # Wait for increment
    assert counter == 1
    event.clear()

    # Stop task
    task.stop()
    await asyncio.sleep(0.1)  # Let stop take effect
    assert counter == 1  # Shouldn't increment after stop

    # Cleanup
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass


async def test_restartable_task_restart():
    # Test restart functionality
    counter = 0
    event = asyncio.Event()

    async def increment_counter():
        nonlocal counter
        counter += 1
        event.set()  # Signal that we've incremented
        await asyncio.sleep(0.1)

    task = RestartableTask(increment_counter)
    start_task = asyncio.create_task(task.start())

    # Let it run once
    await event.wait()
    assert counter == 1
    event.clear()

    # Restart task
    task.restart()
    await event.wait()
    assert counter == 2  # Should increment again after restart
    event.clear()

    # Stop task
    task.stop()
    await asyncio.sleep(0.1)
    assert counter == 2  # Shouldn't increment after stop

    # Cleanup
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass


async def test_restartable_task_cancellation():
    # Test cancellation handling
    counter = 0
    event = asyncio.Event()
    cancelled = False

    async def increment_counter():
        nonlocal counter, cancelled
        try:
            counter += 1
            event.set()  # Signal that we've incremented
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            cancelled = True
            event.set()  # Signal cancellation
            raise

    task = RestartableTask(increment_counter)
    start_task = asyncio.create_task(task.start())

    # Let it run once
    await event.wait()
    assert counter == 1
    assert not cancelled
    event.clear()

    # Cancel task
    task.restart()  # This will cancel the current task
    await event.wait()
    assert cancelled  # Should have been cancelled
    event.clear()

    # Let new task run
    await event.wait()
    assert counter == 2  # Should have restarted and incremented again
    event.clear()

    # Stop task
    task.stop()
    await asyncio.sleep(0.1)
    assert counter == 2  # Shouldn't increment after stop

    # Cleanup
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass


async def test_stop_before_start_assertion():
    """Test stopping a task before it's started should raise assertion error."""

    async def dummy_coro():
        await asyncio.sleep(0.1)

    task = RestartableTask(dummy_coro)

    # Stop before start should raise assertion error due to task being None
    with pytest.raises(AssertionError):
        task.stop()


async def test_restart_before_start_assertion():
    """Test restarting a task before it's started should raise assertion error."""

    async def dummy_coro():
        await asyncio.sleep(0.1)

    task = RestartableTask(dummy_coro)

    # Restart before start should raise assertion error
    with pytest.raises(AssertionError):
        task.restart()


async def test_exception_in_coro_stops_task():
    """Test that exceptions in the coroutine stop the task loop."""
    counter = 0
    exception_occurred = False

    async def failing_coro():
        nonlocal counter, exception_occurred
        counter += 1
        exception_occurred = True
        raise ValueError("Test error")

    task = RestartableTask(failing_coro)
    start_task = asyncio.create_task(task.start())

    # Let it fail
    await asyncio.sleep(0.05)

    # Should have tried once and then stopped due to exception
    assert counter == 1
    assert exception_occurred
    assert start_task.done()

    # Cleanup
    start_task.cancel()
    try:
        await start_task
    except (asyncio.CancelledError, ValueError):
        pass


async def test_task_state_consistency():
    """Test that task state remains consistent through operations."""
    call_count = 0

    async def state_coro():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)

    task = RestartableTask(state_coro)

    # Initial state
    assert task.task is None
    assert not task.stopped

    # Start task
    start_task = asyncio.create_task(task.start())
    await asyncio.sleep(0.01)

    # After start
    assert task.task is not None
    assert not task.stopped
    assert not task.task.done()

    # Restart
    old_task = task.task
    task.restart()
    await asyncio.sleep(0.01)

    # After restart
    assert task.task is not None
    assert task.task != old_task  # New task created
    assert not task.stopped
    assert old_task.cancelled()

    # Stop
    task.stop()
    await asyncio.sleep(0.01)

    # After stop
    assert task.stopped
    assert task.task.cancelled()

    # Cleanup
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass


async def test_zero_delay_coro():
    """Test with a coroutine that completes immediately."""
    completion_count = 0

    async def instant_coro():
        nonlocal completion_count
        completion_count += 1
        # Complete immediately, no await

    task = RestartableTask(instant_coro)
    start_task = asyncio.create_task(task.start())

    # Let it run for a bit - should complete multiple times rapidly
    await asyncio.sleep(0.01)

    # Should have completed multiple times
    initial_count = completion_count
    assert initial_count > 0

    # Stop and verify it stops
    task.stop()
    await asyncio.sleep(0.01)
    final_count = completion_count

    # Should have stopped running
    assert final_count >= initial_count

    # Cleanup
    start_task.cancel()
    try:
        await start_task
    except asyncio.CancelledError:
        pass
