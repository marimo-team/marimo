from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime.kernel import Kernel
from tests.conftest import ExecReqProvider


async def test_pdb_patched(
    execution_kernel: Kernel, exec_req: ExecReqProvider
) -> None:
    k = execution_kernel
    await k.run([exec_req.get("import pdb")])

    pdb = k.globals["pdb"]
    assert pdb.Pdb == MarimoPdb
    assert k.debugger.stdout is k.stdout
    assert k.debugger.stdin is k.stdin
