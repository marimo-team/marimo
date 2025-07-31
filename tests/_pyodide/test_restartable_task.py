import asyncio

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
