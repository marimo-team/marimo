# Copyright 2026 Marimo. All rights reserved.
# ruff: noqa: F403, F405, TID252

from ._shared import *


async def run_marimo_thread_cases():
    async_context_events = []
    async_thread_failures = []
    old_hook = threading.excepthook

    def capture_async_thread_hook(args):
        async_thread_failures.append(
            (args.thread.name, args.exc_type.__name__, str(args.exc_value))
        )

    threading.excepthook = capture_async_thread_hook
    try:

        async def async_context_worker():
            async_context_events.append("started")
            mo.output.append("async mo.Thread started")
            await asyncio.sleep(0)
            async_context_events.append("after-yield")
            mo.output.append("async mo.Thread after yield")
            raise RuntimeError("async mo.Thread context failure")

        async_thread = mo.Thread(
            target=async_context_worker,
            name="async-context-thread",
        )
        async_thread.start()
        async_thread.join(1)
    finally:
        threading.excepthook = old_hook

    mo.output.append("parent output survived async mo.Thread failure")
    assert async_context_events == ["started", "after-yield"]
    assert async_thread_failures == [
        (
            "async-context-thread",
            "RuntimeError",
            "async mo.Thread context failure",
        )
    ]
    record("marimo_thread.async_context_isolation", "api-compatible")

    ui_cell_id = mo._runtime.context.get_context().cell_id
    assert ui_cell_id is not None
    thread_sliders = []

    def ui_worker():
        thread_sliders.append(mo.ui.slider(0, 10))

    ui_thread = mo.Thread(target=ui_worker, name="ui-id-worker")
    ui_thread.start()
    ui_thread.join(1)
    assert not ui_thread.is_alive()
    assert len(thread_sliders) == 1
    assert (
        mo._runtime.context.get_context().ui_element_registry.get_cell(
            thread_sliders[0]._id
        )
        == ui_cell_id
    )
    record("marimo_thread.ui_ids_use_cell_provider", "api-compatible")

    output_messages = []
    current_thread_observations = []
    with mo.status.progress_bar(
        total=3,
        title="mo.Thread output",
        completion_title="mo.Thread output complete",
    ) as progress:

        def output_worker(label):
            current = mo.current_thread()
            assert current is threading.current_thread()
            current_thread_observations.append(
                (current.name, current.should_exit)
            )
            output_messages.append(label)
            mo.output.append(f"mo.Thread output {label}")
            progress.update(subtitle=f"{label} appended")

        output_threads = [
            mo.Thread(
                target=output_worker, args=("alpha",), name="output-alpha"
            ),
            mo.Thread(
                target=output_worker, args=("beta",), name="output-beta"
            ),
            mo.Thread(
                target=output_worker, args=("gamma",), name="output-gamma"
            ),
        ]
        for thread in output_threads:
            thread.start()
        for thread in output_threads:
            thread.join(1)

    mo.output.append("parent output survived mo.Thread output workers")
    assert sorted(output_messages) == ["alpha", "beta", "gamma"]
    assert sorted(current_thread_observations) == [
        ("output-alpha", False),
        ("output-beta", False),
        ("output-gamma", False),
    ]
    assert progress.current == 3
    assert progress.closed is True
    record("marimo_thread.current_thread_should_exit", "api-compatible")
    record("marimo_thread.shared_output_progress", "api-compatible")

    parent_ctx = mo._runtime.context.get_context()
    child_count_before = len(parent_ctx.children)
    child_app_records = []

    async def child_app_worker():
        app = mo.App()

        @app.cell
        def _():
            embedded_value = "thread child app"
            return (embedded_value,)

        result = await app.embed()
        child_app_records.append(
            {
                "value": result.defs["embedded_value"],
            }
        )

    child_app_thread = mo.Thread(
        target=child_app_worker,
        name="child-app-worker",
    )
    child_app_thread.start()
    child_app_thread.join(1)
    assert not child_app_thread.is_alive()
    assert child_app_records == [
        {
            "value": "thread child app",
        }
    ]
    assert len(parent_ctx.children) == child_count_before + 1
    record("marimo_thread.child_app_embed_parent_ownership", "api-compatible")
