# Copyright 2026 Marimo. All rights reserved.
# ruff: noqa: F403, F405, PT017, TID252

from ._shared import *


async def run_futures_cases():
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future = executor.submit(lambda: 21 * 2)
        assert future.result(timeout=1) == 42

        def failing_future():
            raise ValueError("future boom")

        try:
            executor.submit(failing_future).result(timeout=1)
        except ValueError as exc:
            assert str(exc) == "future boom"
        else:
            raise AssertionError("future exception was not raised by result()")

        cancelled = executor.submit(lambda: "should not run")
        assert cancelled.cancel()
        try:
            cancelled.result(timeout=1)
        except CancelledError:
            pass
        else:
            raise AssertionError("cancelled future returned a result")
    record("futures.thread_pool_result_exception_cancel", "serialized")

    executor_context = contextvars.ContextVar(
        "executor_context", default="unset"
    )
    executor_context.set("parent")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(lambda: executor_context.get()).result(1) == (
            "unset"
        )
    assert executor_context.get() == "parent"
    record("futures.thread_pool_contextvars_not_inherited", "serialized")

    def executor_thread_surface_worker():
        current = threading.current_thread()
        return (
            isinstance(current, threading.Thread),
            current.ident is not None,
            current.is_alive(),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(executor_thread_surface_worker).result(1) == (
            True,
            True,
            True,
        )
    record("futures.thread_pool_current_thread_surface", "api-compatible")

    async def executor_returned_coroutine():
        return "awaited elsewhere"

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        returned_coroutine = executor.submit(
            lambda: executor_returned_coroutine()
        ).result(1)
    assert inspect.iscoroutine(returned_coroutine)
    returned_coroutine.close()
    record("futures.thread_pool_awaitable_return_value", "api-compatible")

    assert await asyncio.to_thread(lambda: 42) == 42
    record("asyncio.to_thread_result", "serialized")

    to_thread_context = contextvars.ContextVar(
        "to_thread_context", default="unset"
    )
    to_thread_context.set("parent")
    assert await asyncio.to_thread(lambda: to_thread_context.get()) == "parent"
    assert to_thread_context.get() == "parent"
    record("asyncio.to_thread_contextvars_inherited", "serialized")

    loop = asyncio.get_running_loop()
    assert await loop.run_in_executor(None, lambda: 42) == 42
    record("asyncio.run_in_executor_default", "serialized")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        assert await loop.run_in_executor(executor, lambda: 43) == 43
    record("asyncio.run_in_executor_thread_pool", "serialized")

    ticker_stop = False
    ticker_count = {"value": 0}

    async def ticker():
        while not ticker_stop:
            ticker_count["value"] += 1
            await asyncio.sleep(0)

    ticker_task = asyncio.create_task(ticker())
    cooperative_event = threading.Event()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        cooperative_future = executor.submit(cooperative_event.wait, 1)
        release_thread = start_delayed_thread(
            "futures-cooperative-event",
            cooperative_event.set,
        )
        assert cooperative_future.result(timeout=1) is True
        release_thread.join(1)
        assert not release_thread.is_alive()
    ticker_stop = True
    await ticker_task
    assert ticker_count["value"] > 0
    record("futures.executor_callback_cooperative_wait", "cooperative-only")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        assert list(executor.map(lambda value: value + 1, [1, 2, 3])) == [
            2,
            3,
            4,
        ]
        buffered_values_consumed = []

        def buffered_values():
            buffered_values_consumed.append(1)
            yield 1
            buffered_values_consumed.append(2)
            yield 2

        buffered_results = executor.map(
            lambda value: value,
            buffered_values(),
            buffersize=1,
        )
        assert buffered_values_consumed == [1]
        assert next(buffered_results) == 1
        assert buffered_values_consumed == [1, 2]
        assert list(buffered_results) == [2]
    record("futures.thread_pool_map_ordered", "serialized")

    callback_records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        callback_future = executor.submit(lambda: 9)
        callback_future.add_done_callback(
            lambda future: callback_records.append(future.result(timeout=0))
        )
    assert callback_future.result(timeout=1) == 9
    assert callback_records == [9]
    record("futures.callback_once", "api-compatible")

    exception_callback_records = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

        def callback_failure():
            raise RuntimeError("callback failure")

        exception_callback_future = executor.submit(callback_failure)
        exception_callback_future.add_done_callback(
            lambda future: exception_callback_records.append(
                type(future.exception(timeout=0)).__name__
            )
        )
        try:
            exception_callback_future.result(timeout=1)
        except RuntimeError as exc:
            assert str(exc) == "callback failure"
        else:
            raise AssertionError("exception future returned a value")
    assert exception_callback_records == ["RuntimeError"]
    record("futures.callback_once_exception", "api-compatible")

    initializer_records = []
    initializer_local = threading.local()

    def executor_initializer(label):
        initializer_records.append(label)
        initializer_local.ready = True
        initializer_local.count = 0

    def initialized_work():
        initializer_local.count += 1
        return (
            threading.current_thread().name,
            initializer_local.ready,
            initializer_local.count,
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=3,
        thread_name_prefix="matrix-lane",
        initializer=executor_initializer,
        initargs=("thread-init",),
    ) as executor:
        first_initializer_result = executor.submit(initialized_work).result(
            timeout=1
        )
        second_initializer_result = executor.submit(initialized_work).result(
            timeout=1
        )
        assert list(
            executor.map(lambda value: value + 1, [1, 2], chunksize=4)
        ) == [2, 3]
    assert initializer_records == ["thread-init"]
    assert first_initializer_result[0] == second_initializer_result[0]
    assert first_initializer_result[1:] == (True, 1)
    assert second_initializer_result[1:] == (True, 2)
    record("futures.thread_pool_initializer_chunksize", "serialized")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(lambda value=value: value) for value in range(3)
        ]
        done, not_done = concurrent.futures.wait(
            futures,
            timeout=1,
            return_when=concurrent.futures.ALL_COMPLETED,
        )
        assert done == set(futures)
        assert not not_done
    record("futures.wait_all_completed", "api-compatible")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        fast = executor.submit(lambda: "fast")
        slow_release = threading.Event()
        slow = executor.submit(
            lambda: "slow" if slow_release.wait(1) else "timeout"
        )
        done, not_done = concurrent.futures.wait(
            [fast, slow],
            timeout=1,
            return_when=concurrent.futures.FIRST_COMPLETED,
        )
        assert fast in done
        assert fast.result(timeout=0) == "fast"
        assert slow in not_done
        slow_release.set()
        assert slow.result(timeout=1) == "slow"
    record("futures.wait_first_completed", "cooperative-only")

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:

        def raises_first():
            raise ValueError("first exception")

        failed = executor.submit(raises_first)
        delayed = executor.submit(
            lambda: run_sync(marimoWasmConcurrencyDelay("delayed", 5))
        )
        done, _not_done = concurrent.futures.wait(
            [failed, delayed],
            timeout=1,
            return_when=concurrent.futures.FIRST_EXCEPTION,
        )
        assert failed in done
        assert isinstance(failed.exception(timeout=0), ValueError)
    record("futures.wait_first_exception", "cooperative-only")

    negative_timeout_executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=1
    )
    negative_timeout_release = threading.Event()
    try:
        negative_timeout_started = threading.Event()

        def wait_for_negative_timeout_release():
            negative_timeout_started.set()
            negative_timeout_release.wait()
            return "negative-timeout"

        negative_timeout_future = negative_timeout_executor.submit(
            wait_for_negative_timeout_release
        )
        assert negative_timeout_started.wait(1)
        assert not negative_timeout_future.done()
        try:
            assert_run_sync_not_called(
                lambda: negative_timeout_future.result(timeout=-1)
            )
        except concurrent.futures.TimeoutError:
            pass
        else:
            raise AssertionError("Future.result negative timeout did not poll")
        record(
            "futures.future_result_negative_timeout_immediate",
            "api-compatible",
        )

        try:
            assert_run_sync_not_called(
                lambda: negative_timeout_future.exception(timeout=-1)
            )
        except concurrent.futures.TimeoutError:
            pass
        else:
            raise AssertionError(
                "Future.exception negative timeout did not poll"
            )
        record(
            "futures.future_exception_negative_timeout_immediate",
            "api-compatible",
        )

        done, not_done = assert_run_sync_not_called(
            lambda: concurrent.futures.wait(
                [negative_timeout_future], timeout=-1
            )
        )
        assert not done
        assert not_done == {negative_timeout_future}
        record("futures.wait_negative_timeout_immediate", "api-compatible")

        try:
            assert_run_sync_not_called(
                lambda: next(
                    concurrent.futures.as_completed(
                        [negative_timeout_future], timeout=-1
                    )
                )
            )
        except concurrent.futures.TimeoutError:
            pass
        else:
            raise AssertionError(
                "as_completed negative timeout did not raise TimeoutError"
            )
        record(
            "futures.as_completed_negative_timeout_immediate", "api-compatible"
        )

        negative_timeout_release.set()
        assert negative_timeout_future.result(timeout=1) == "negative-timeout"
    finally:
        negative_timeout_release.set()
        negative_timeout_executor.shutdown()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(lambda value=value: value) for value in range(3)
        ]
        assert sorted(
            future.result(timeout=0)
            for future in concurrent.futures.as_completed(futures, timeout=1)
        ) == [0, 1, 2]
    record("futures.as_completed", "api-compatible")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        done_future = executor.submit(lambda: "done")
        assert done_future.result(timeout=1) == "done"
        assert list(
            concurrent.futures.as_completed([done_future], timeout=0)
        ) == [done_future]
    record("futures.as_completed_timeout_zero_done", "api-compatible")

    cancel_event = threading.Event()
    running_started = threading.Event()
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        running_future = executor.submit(
            lambda: (running_started.set(), cancel_event.wait(1))[-1]
        )
        assert running_started.wait(1)
        queued_future = executor.submit(lambda: "queued")
        executor.shutdown(wait=False, cancel_futures=True)
        assert queued_future.cancelled()
        cancel_event.set()
        assert running_future.result(timeout=1) is True
    finally:
        executor.shutdown(wait=True)
    record("futures.shutdown_cancel_futures", "cooperative-only")
