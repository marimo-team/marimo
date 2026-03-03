from unittest.mock import patch

from marimo._messaging.cell_output import PDB_START_MESSAGE, CellChannel
from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider, _MockStream


async def test_pdb_patched(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run([exec_req.get("import pdb")])

    pdb = k.globals["pdb"]
    assert pdb.Pdb == MarimoPdb
    assert k.debugger.stdout is k.stdout
    assert k.debugger.stdin is k.stdin


async def test_pdb_request_broadcasts_start(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel

    # Run a cell that raises an exception so the debugger stores a traceback
    er = exec_req.get("raise ValueError('test')")
    await k.run([er])
    cell_id = er.cell_id

    assert k.debugger is not None
    assert cell_id in k.debugger._last_tracebacks

    stream: _MockStream = k.stream  # type: ignore[assignment]
    notifications_before = len(stream.cell_notifications)

    # Mock post_mortem_by_cell_id to avoid entering the interactive pdb loop
    with patch.object(k.debugger, "post_mortem_by_cell_id"):
        await k.pdb_request(cell_id)

    new_notifications = stream.cell_notifications[notifications_before:]
    pdb_starts = [
        n
        for n in new_notifications
        if not isinstance(n.console, list)
        and n.console is not None
        and n.console.channel == CellChannel.PDB
        and n.console.data == PDB_START_MESSAGE
    ]
    assert len(pdb_starts) == 1
    assert pdb_starts[0].cell_id == cell_id
