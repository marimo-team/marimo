from marimo._runtime.marimo_pdb import MarimoPdb
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def test_pdb_patched(k: Kernel, exec_req: ExecReqProvider):
    k.run([exec_req.get("import pdb")])

    pdb = k.globals["pdb"]
    assert pdb.Pdb == MarimoPdb
    assert k._debugger.stdout is k.stdout
    assert k._debugger.stdin is k.stdin
