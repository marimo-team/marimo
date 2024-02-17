from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_pdb_patched(k: Kernel, exec_req: ExecReqProvider):
    await k.run([exec_req.get("import pdb")])

    pdb = k.globals["pdb"]
    assert pdb.Pdb == MarimoPdb
    assert k.debugger.stdout is k.stdout
    assert k.debugger.stdin is k.stdin
