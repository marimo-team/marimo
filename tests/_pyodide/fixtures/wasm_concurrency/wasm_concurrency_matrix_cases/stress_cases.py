# Copyright 2026 Marimo. All rights reserved.
# ruff: noqa: F403, F405, TID252

from ._shared import *


async def run_stress_cases():
    import multiprocessing

    loop_stop = threading.Event()
    loop_count = {"value": 0}

    def daemon_loop():
        while not loop_stop.is_set():
            loop_count["value"] += 1
            if loop_count["value"] >= 3:
                loop_stop.set()

    daemon = threading.Thread(target=daemon_loop, daemon=True)
    daemon.start()
    daemon.join(1)
    assert loop_count["value"] >= 3
    record("threading.daemon_loop_run_to_completion", "api-compatible")

    process_queue = multiprocessing.Queue()

    def process_worker(output):
        output.put(("process", threading.current_thread().name))

    process = multiprocessing.Process(
        target=process_worker, args=(process_queue,)
    )
    process.start()
    process.join(1)
    assert process.exitcode == 0
    assert process_queue.get(timeout=1)[0] == "process"
    record("multiprocessing.process_queue", "serialized")

    process_context = contextvars.ContextVar(
        "process_context", default="unset"
    )
    process_context.set("parent")
    process_context_queue = multiprocessing.Queue()

    def process_context_worker(output):
        output.put(process_context.get())
        process_context.set("child")
        output.put(process_context.get())

    context_process = multiprocessing.Process(
        target=process_context_worker, args=(process_context_queue,)
    )
    context_process.start()
    context_process.join(1)
    assert context_process.exitcode == 0
    assert process_context_queue.get(timeout=1) == "unset"
    assert process_context_queue.get(timeout=1) == "child"
    assert process_context.get() == "parent"
    record("multiprocessing.process_contextvars_not_inherited", "serialized")

    shared_values = []
    shared_process = multiprocessing.Process(
        target=lambda values: values.append("child"),
        args=(shared_values,),
    )
    shared_process.start()
    shared_process.join(1)
    assert shared_process.exitcode == 0
    assert shared_values == ["child"]
    reference_queue = multiprocessing.Queue()
    reference_value = {"items": []}
    reference_queue.put(reference_value)
    reference_value["items"].append("parent-mutation")
    received_reference = reference_queue.get(timeout=1)
    assert received_reference is reference_value
    assert received_reference == {"items": ["parent-mutation"]}
    record("multiprocessing.process_queue_reference_semantics", "serialized")

    interrupt_event = threading.Event()
    interrupted = multiprocessing.Process(target=interrupt_event.wait)
    interrupted.start()
    run_sync(marimoWasmConcurrencyDelay("allow-block", 1))
    interrupted.kill()
    # `kill()` is cooperative, so release the blocked wait before teardown.
    interrupt_event.set()
    interrupted.join(1)
    assert interrupted.exitcode == -1
    assert not interrupted.is_alive()
    record("multiprocessing.process_kill_cooperative", "cooperative-only")

    bad_process = multiprocessing.Process(
        target=lambda: (_ for _ in ()).throw(RuntimeError("process boom"))
    )
    bad_process.start()
    bad_process.join(1)
    assert bad_process.exitcode == 1
    record("multiprocessing.process_exception_exitcode", "serialized")

    for cycle in range(4):
        bounded_stress_queue = queue.Queue(maxsize=2)
        bounded_stress_queue.put_nowait(("cycle", cycle))
        bounded_stress_queue.put_nowait(("cycle", cycle + 1))
        assert bounded_stress_queue.full()
        try:
            bounded_stress_queue.put_nowait("overflow")
        except queue.Full:
            pass
        else:
            raise AssertionError("bounded stress queue did not raise Full")
        assert bounded_stress_queue.get_nowait() == ("cycle", cycle)
        bounded_stress_queue.put(("cycle", cycle + 2), timeout=0)
        assert bounded_stress_queue.get(timeout=0) == ("cycle", cycle + 1)
        assert bounded_stress_queue.get(timeout=0) == ("cycle", cycle + 2)

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            assert list(
                executor.map(
                    lambda value, cycle=cycle: value + cycle, range(6)
                )
            ) == [value + cycle for value in range(6)]

    record("stress.thread_pool_queue_primitives", "serialized")

    for cycle in range(4):
        bounded_process_queue = multiprocessing.Queue(maxsize=2)
        bounded_process_queue.put_nowait(("cycle", cycle))
        bounded_process_queue.put_nowait(("cycle", cycle + 1))
        assert bounded_process_queue.full()
        try:
            bounded_process_queue.put_nowait("overflow")
        except queue.Full:
            pass
        else:
            raise AssertionError("bounded process queue did not raise Full")
        assert bounded_process_queue.get_nowait() == ("cycle", cycle)
        bounded_process_queue.put(("cycle", cycle + 2), timeout=0)
        assert bounded_process_queue.get(timeout=0) == (
            "cycle",
            cycle + 1,
        )
        assert bounded_process_queue.get(timeout=0) == (
            "cycle",
            cycle + 2,
        )

        with multiprocessing.Pool(4) as pool:
            assert pool.map(
                lambda value, cycle=cycle: value + cycle, range(6)
            ) == [value + cycle for value in range(6)]

        stress_event = threading.Event()
        stress_process = multiprocessing.Process(target=stress_event.wait)
        stress_process.start()
        run_sync(marimoWasmConcurrencyDelay("stress-process", 1))
        assert stress_process.is_alive()
        stress_process.terminate()
        # `terminate()` has the same cooperative cancellation boundary.
        stress_event.set()
        stress_process.join(1)
        assert stress_process.exitcode == -1
        assert not stress_process.is_alive()
    record("stress.process_shaped_primitives", "serialized")
