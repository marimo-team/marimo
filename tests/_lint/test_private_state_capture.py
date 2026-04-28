from __future__ import annotations

from pathlib import Path

from marimo._lint import run_check


def test_private_state_capture_warns_on_captured_cache(tmp_path) -> None:
    notebook_file = Path(tmp_path) / "cached.py"
    notebook_file.write_text(
        '''import marimo

__generated_with = "0.23.2"
app = marimo.App()


@app.cell
def __():
    _cache = dict()

    def square(x):
        if x in _cache:
            return _cache[x] + 1
        res = x * x
        _cache[x] = res
        return res

    return (square,)


if __name__ == "__main__":
    app.run()
'''
    )

    linter = run_check((str(notebook_file),), formatter="json")
    result = linter.get_json_result()

    assert result["summary"]["files_with_issues"] == 1
    issue = result["issues"][0]
    assert issue["code"] == "MR004"
    assert issue["severity"] == "runtime"
    assert "private cell-local variable" in issue["message"]
    assert "square" in issue["message"]
