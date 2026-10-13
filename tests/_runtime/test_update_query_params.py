# Copyright 2026 Marimo. All rights reserved.
"""Kernel behaviour when the browser URL's query params change.

Browser back/forward navigation restores a URL the kernel never set. The
frontend reports the restored params with `UpdateQueryParamsCommand`; the
kernel must adopt them and re-run the cells that read `mo.query_params()`,
without echoing them back (the URL is already correct).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._runtime.commands import UpdateQueryParamsCommand
from tests._messaging.mocks import MockStream

if TYPE_CHECKING:
    from marimo._runtime.runtime import Kernel
    from tests.conftest import ExecReqProvider, MockedKernel


async def _run_reader(k: Kernel, exec_req: ExecReqProvider) -> None:
    """Three cells: import, bind the params, and a reader that logs reads."""
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("seen = []"),
            exec_req.get("params = mo.query_params()"),
            exec_req.get(
                "seen.append(params.get('tab')); tab = params.get('tab')"
            ),
        ]
    )


class TestUpdateQueryParams:
    async def test_reruns_cells_that_read_query_params(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await _run_reader(k, exec_req)
        assert k.globals["tab"] is None

        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "b"})
        )

        assert k.globals["tab"] == "b"
        assert k.query_params.to_dict() == {"tab": "b"}

    async def test_replaces_all_params_not_just_the_sent_ones(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await _run_reader(k, exec_req)
        await k.update_query_params(
            UpdateQueryParamsCommand(
                query_params={"tab": "b", "ids": ["1", "2"]}
            )
        )
        # Going "back" to a URL without `ids` must drop it.
        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "a"})
        )

        assert k.query_params.to_dict() == {"tab": "a"}
        assert k.globals["tab"] == "a"

    async def test_does_not_echo_params_to_frontend(
        self, mocked_kernel: MockedKernel, exec_req: ExecReqProvider
    ) -> None:
        k = mocked_kernel.k
        await _run_reader(k, exec_req)

        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "b"})
        )

        # A query-params-* notification would make the frontend push a
        # second history entry for a URL the browser already restored.
        ops = [m["op"] for m in MockStream(mocked_kernel.stream).operations]
        assert not any(op.startswith("query-params-") for op in ops)

    async def test_unchanged_params_do_not_rerun(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await _run_reader(k, exec_req)
        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "b"})
        )
        assert k.globals["seen"] == [None, "b"]

        # e.g. a hash-only navigation also fires popstate.
        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "b"})
        )

        assert k.globals["seen"] == [None, "b"]

    async def test_ignores_session_and_token_keys(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await _run_reader(k, exec_req)

        await k.update_query_params(
            UpdateQueryParamsCommand(
                query_params={
                    "tab": "b",
                    "session_id": "s-1",
                    "access_token": "secret",
                    "refresh_token": "secret",
                }
            )
        )

        # Same filter the session applies when the kernel starts.
        assert k.query_params.to_dict() == {"tab": "b"}

    async def test_only_ignored_keys_changing_does_not_rerun(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await _run_reader(k, exec_req)
        runs_before = list(k.globals["seen"])

        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"session_id": "s-2"})
        )

        assert k.globals["seen"] == runs_before

    async def test_does_not_rerun_the_cell_that_binds_the_params(
        self, k: Kernel, exec_req: ExecReqProvider
    ) -> None:
        await k.run(
            [
                exec_req.get("import marimo as mo"),
                exec_req.get("binds = []"),
                exec_req.get("params = mo.query_params(); binds.append(1)"),
                exec_req.get("tab = params.get('tab')"),
            ]
        )

        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "b"})
        )

        assert k.globals["tab"] == "b"
        assert k.globals["binds"] == [1]

    async def test_lazy_kernel_marks_readers_stale_instead_of_running(
        self, lazy_kernel: Kernel, exec_req: ExecReqProvider
    ) -> None:
        k = lazy_kernel
        import_cell = exec_req.get("import marimo as mo")
        bind_cell = exec_req.get("params = mo.query_params()")
        reader_cell = exec_req.get("tab = params.get('tab')")
        await k.run([import_cell, bind_cell, reader_cell])
        assert not k.graph.cells[reader_cell.cell_id].stale

        await k.update_query_params(
            UpdateQueryParamsCommand(query_params={"tab": "b"})
        )

        assert k.query_params.to_dict() == {"tab": "b"}
        assert k.graph.cells[reader_cell.cell_id].stale
        assert not k.graph.cells[bind_cell.cell_id].stale
        assert k.globals["tab"] is None
