# Copyright 2026 Marimo. All rights reserved.
# ruff: noqa: F403, F405, TID252

from ._shared import *


async def run_threading_and_queue_cases():
    import asyncio as imported_asyncio
    import logging as imported_logging
    import queue as imported_queue

    assert imported_logging.getLogger("wasm.threading")
    q = imported_queue.Queue()
    q.put("ok")
    assert q.get(block=False) == "ok"
    assert imported_asyncio.Queue is not None
    record("install.stdlib_imports_after_patch", "api-compatible")

    assert isinstance(threading.current_thread(), threading.Thread)
    assert isinstance(threading.main_thread(), threading.Thread)
    assert not isinstance(threading.current_thread(), mo.Thread)
    try:
        mo.current_thread()
    except RuntimeError:
        pass
    else:
        raise AssertionError("main thread was treated as a marimo Thread")
    record("threading.main_thread_instance_check", "api-compatible")

    immediate_event = threading.Event()
    assert (
        assert_run_sync_not_called(lambda: immediate_event.wait(timeout=-1))
        is False
    )
    record("threading.event_negative_timeout_immediate", "api-compatible")

    negative_join_release = asyncio.Event()

    async def negative_join_target():
        await negative_join_release.wait()

    negative_join_thread = threading.Thread(target=negative_join_target)
    negative_join_thread.start()
    assert negative_join_thread.is_alive()
    assert_run_sync_not_called(lambda: negative_join_thread.join(timeout=-1))
    assert negative_join_thread.is_alive()
    negative_join_release.set()
    negative_join_thread.join(timeout=1)
    assert not negative_join_thread.is_alive()
    record(
        "threading.thread_join_negative_timeout_immediate", "api-compatible"
    )

    event = threading.Event()
    event_results = []

    def event_worker():
        assert event.wait(1)
        event_results.append(threading.current_thread().name)

    event_thread = threading.Thread(target=event_worker, name="event-worker")
    event_thread.start()
    delayed_event_thread = start_delayed_thread(
        "threading-event-set",
        event.set,
    )
    event_thread.join(1)
    delayed_event_thread.join(1)
    assert event_results == ["event-worker"]
    assert not event_thread.is_alive()
    assert not delayed_event_thread.is_alive()
    record("threading.event_wait_delayed_thread", "cooperative-only")

    bounded_queue = queue.Queue(maxsize=1)
    bounded_queue.put("first", block=False)
    try:
        bounded_queue.put("second", block=False)
    except queue.Full:
        pass
    else:
        raise AssertionError("bounded queue did not raise Full")
    assert bounded_queue.get(block=False) == "first"
    simple_queue = queue.SimpleQueue()
    simple_queue.put("simple")
    assert simple_queue.get() == "simple"
    record("queue.bounded_simplequeue_immediate", "api-compatible")

    local = threading.local()
    local_results = []

    def local_worker(value):
        local.value = value
        local_results.append((threading.current_thread().name, local.value))

    threads = [
        threading.Thread(target=local_worker, args=(1,), name="local-one"),
        threading.Thread(target=local_worker, args=(2,), name="local-two"),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(1)
    assert sorted(local_results) == [("local-one", 1), ("local-two", 2)]
    assert not hasattr(local, "value")
    record("threading.local_isolation", "api-compatible")

    ambient_context = contextvars.ContextVar("ambient", default="unset")
    ambient_context.set("parent")
    contextvar_records = []

    def contextvar_worker():
        contextvar_records.append(ambient_context.get())
        ambient_context.set("child")
        contextvar_records.append(ambient_context.get())

    contextvar_thread = threading.Thread(target=contextvar_worker)
    contextvar_thread.start()
    contextvar_thread.join(1)
    assert not contextvar_thread.is_alive()
    assert contextvar_records == ["unset", "child"]
    assert ambient_context.get() == "parent"
    record("threading.contextvars_not_inherited", "api-compatible")

    identity_event = threading.Event()
    identity_release = threading.Event()
    identity_records = []

    def identity_worker():
        current = threading.current_thread()
        record = {
            "name": current.name,
            "ident": current.ident,
            "native_id": current.native_id,
            "get_ident": threading.get_ident(),
            "get_native_id": threading.get_native_id(),
        }
        if hasattr(threading, "currentThread"):
            record["legacy_name"] = threading.currentThread().name
        if hasattr(threading, "activeCount"):
            record["legacy_active_count"] = threading.activeCount()
        identity_records.append(record)
        identity_event.set()
        identity_release.wait(1)

    before_active = threading.active_count()
    identity_thread = threading.Thread(
        target=identity_worker, name="identity-worker"
    )
    identity_thread.start()
    assert identity_event.wait(1)
    active_names = {thread.name for thread in threading.enumerate()}
    assert "identity-worker" in active_names
    assert threading.active_count() >= before_active
    identity_release.set()
    identity_thread.join(1)
    assert not identity_thread.is_alive()
    assert identity_records[0]["name"] == "identity-worker"
    assert identity_records[0]["ident"] == identity_records[0]["get_ident"]
    assert (
        identity_records[0]["native_id"]
        == identity_records[0]["get_native_id"]
    )
    if "legacy_name" in identity_records[0]:
        assert identity_records[0]["legacy_name"] == "identity-worker"
    if "legacy_active_count" in identity_records[0]:
        assert identity_records[0]["legacy_active_count"] >= before_active
    assert threading.main_thread().name == "MainThread"
    record("threading.identity_enumerate_active_count", "api-compatible")

    direct_run_records = []
    direct_thread = threading.Thread(
        target=lambda: direct_run_records.append(
            threading.current_thread().name
        ),
        name="direct-run-thread",
    )
    direct_thread.run()
    assert direct_run_records == [threading.current_thread().name]
    record("threading.thread_run_direct_identity", "api-compatible")

    class CountingLocal(threading.local):
        def __init__(self):
            self.created = getattr(self, "created", 0) + 1
            self.value = "unset"

    counting_local = CountingLocal()
    counting_records = [("main", counting_local.created, counting_local.value)]

    def counting_worker(value):
        counting_local.value = value
        counting_records.append(
            (
                threading.current_thread().name,
                getattr(counting_local, "created", None),
                counting_local.value,
            )
        )

    counting_threads = [
        threading.Thread(
            target=counting_worker, args=("alpha",), name="counting-alpha"
        ),
        threading.Thread(
            target=counting_worker, args=("beta",), name="counting-beta"
        ),
    ]
    for thread in counting_threads:
        thread.start()
    for thread in counting_threads:
        thread.join(1)
    assert sorted(counting_records) == [
        ("counting-alpha", 1, "alpha"),
        ("counting-beta", 1, "beta"),
        ("main", 1, "unset"),
    ]
    record("threading.local_subclass_init_per_thread", "api-compatible")

    class DefaultLocal(threading.local):
        value = "default"

    default_local = DefaultLocal()
    assert default_local.value == "default"
    default_local.value = "main"
    assert default_local.value == "main"
    default_records = []

    def default_local_worker():
        default_records.append(default_local.value)
        default_local.value = "worker"
        default_records.append(default_local.value)

    default_thread = threading.Thread(target=default_local_worker)
    default_thread.start()
    default_thread.join(1)
    assert default_records == ["default", "worker"]
    assert default_local.value == "main"
    record("threading.local_subclass_defaults", "api-compatible")

    class PropertyLocal(threading.local):
        @property
        def value(self):
            return getattr(self, "_value", "default")

        @value.setter
        def value(self, value):
            self._value = value

    property_local = PropertyLocal()
    assert property_local.value == "default"
    property_local.value = "main"
    property_records = []

    def property_local_worker():
        property_records.append(property_local.value)
        property_local.value = "worker"
        property_records.append(property_local.value)

    property_thread = threading.Thread(target=property_local_worker)
    property_thread.start()
    property_thread.join(1)
    assert property_records == ["default", "worker"]
    assert property_local.value == "main"

    class SlotLocal(threading.local):
        __slots__ = ("value",)

    slot_local = SlotLocal()
    slot_local.value = "main"
    slot_records = []

    def slot_local_worker():
        slot_records.append(slot_local.value)
        slot_local.value = "worker"
        slot_records.append(slot_local.value)

    slot_thread = threading.Thread(target=slot_local_worker)
    slot_thread.start()
    slot_thread.join(1)
    assert slot_records == ["main", "worker"]
    assert slot_local.value == "worker"
    record("threading.local_subclass_descriptors", "api-compatible")

    hook_records = []
    old_hook = threading.excepthook

    def capture_hook(args):
        hook_records.append(
            (args.thread.name, args.exc_type.__name__, str(args.exc_value))
        )

    threading.excepthook = capture_hook
    try:

        def failing_thread():
            raise RuntimeError("thread boom")

        t = threading.Thread(target=failing_thread, name="failing-thread")
        t.start()
        t.join(1)
    finally:
        threading.excepthook = old_hook
    assert hook_records == [("failing-thread", "RuntimeError", "thread boom")]
    record("threading.excepthook", "api-compatible")
