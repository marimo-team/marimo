# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import sys

import pytest

from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


class TestAsyncIO:
    @staticmethod
    async def test_toplevel_await_allowed(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    await asyncio.sleep(0)
                    ran = True
                    """
                ),
            ]
        )
        assert k.globals["ran"]

    @staticmethod
    async def test_toplevel_gather(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    l = []
                    async def f():
                        l.append(1)
                        await asyncio.sleep(0.1)
                        l.append(2)

                    import asyncio
                    await asyncio.gather(f(), f())
                    """
                ),
            ]
        )
        assert k.globals["l"] == [1, 1, 2, 2]

    @staticmethod
    async def test_wait_for(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        import asyncio

        k = any_kernel

        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    async def eternity():
                        await asyncio.sleep(3600)

                    e = None
                    try:
                        await asyncio.wait_for(eternity(), timeout=0)
                    except asyncio.exceptions.TimeoutError as exc:
                        e = exc
                    """
                ),
            ]
        )
        assert not k.errors
        assert isinstance(k.globals["e"], asyncio.exceptions.TimeoutError)

    @staticmethod
    async def test_await_future(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    future = asyncio.Future()
                    future.set_result(1)
                    """
                ),
                exec_req.get(
                    """
                    result = await future
                    """
                ),
            ]
        )
        assert k.globals["result"] == 1
        assert k.globals["future"].done()

    @staticmethod
    async def test_await_future_complex(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    """
                ),
                exec_req.get(
                    """
                    async def set_after(fut, delay, value):
                        await asyncio.sleep(delay)
                        fut.set_result(value)
                    """
                ),
                exec_req.get(
                    """
                    fut = asyncio.Future()
                    asyncio.create_task(set_after(fut, 0.01, "done"))
                    result = await fut
                    """
                ),
            ]
        )
        assert k.globals["result"] == "done"

    @staticmethod
    async def test_run_in_default_executor(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    """
                ),
                exec_req.get(
                    """
                    def blocking():
                        return "done"
                    """
                ),
                exec_req.get(
                    """
                    res = await asyncio.get_running_loop().run_in_executor(
                        None, blocking)
                    """
                ),
            ]
        )
        assert k.globals["res"] == "done"

    @staticmethod
    async def test_run_in_threadpool_executor(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    import concurrent.futures
                    """
                ),
                exec_req.get(
                    """
                    def blocking():
                        return "done"
                    """
                ),
                exec_req.get(
                    """
                    loop = asyncio.get_running_loop()
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        res = await loop.run_in_executor(pool, blocking)
                    """
                ),
            ]
        )
        assert k.globals["res"] == "done"

    @staticmethod
    @pytest.mark.xfail(
        condition=sys.platform == "win32" or sys.platform == "darwin",
        reason=(
            "Bug in interaction with multiprocessing on Windows, macOS; "
            "doesn't work in Jupyter either."
        ),
    )
    async def test_run_in_processpool_executor(
        any_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = any_kernel
        await k.run(
            [
                exec_req.get(
                    """
                    import asyncio
                    import concurrent.futures
                    """
                ),
                exec_req.get(
                    """
                    def blocking():
                        return "done"
                    """
                ),
                exec_req.get(
                    """
                    loop = asyncio.get_running_loop()
                    with concurrent.futures.ProcessPoolExecutor() as pool:
                        res = await loop.run_in_executor(pool, blocking)
                    """
                ),
            ]
        )
        assert not k.errors
        assert k.globals["res"] == "done"
