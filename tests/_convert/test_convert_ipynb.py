import pathlib
import re

import pytest

from marimo._convert.converters import MarimoConvert
from marimo._convert.ipynb import convert_from_ipynb_to_notebook_ir
from tests.mocks import snapshotter

SELF_DIR = pathlib.Path(__file__).parent
snapshot_test = snapshotter(__file__)


@pytest.mark.parametrize(
    "ipynb_path", (SELF_DIR / "ipynb_data").glob("*.ipynb")
)
def test_marimo_convert_snapshots(ipynb_path: pathlib.Path) -> None:
    """Test marimo convert against all notebook fixtures using snapshots."""
    contents = ipynb_path.read_text()
    ir = convert_from_ipynb_to_notebook_ir(contents)
    converted = MarimoConvert.from_ir(ir).to_py()

    converted = re.sub(r"__generated_with = .*\n", "", converted)
    converted = re.sub(r"# requires-python = .*\n", "", converted)

    snapshot_name = f"convert_{ipynb_path.name.replace('.ipynb', '.py.txt')}"
    snapshot_test(snapshot_name, converted)
