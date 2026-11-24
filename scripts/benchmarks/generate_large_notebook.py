# Copyright 2026 Marimo. All rights reserved.
"""Generate large marimo notebooks for performance benchmarks.

Shapes:

- `smoke`: mirrors a release smoke-test notebook. A setup cell, then
  alternating hidden markdown cells and named code cells that only use
  private variables, so every cell depends on the setup cell alone.
- `outputs`: like `smoke`, but every code cell renders an output
  (markdown, plain values, tables, UI elements, stdout).
- `chain`: a linear dependency chain, where each cell reads the variable
  defined by the previous cell.

Usage:

    python scripts/benchmarks/generate_large_notebook.py OUT.py \
        --cells 500 --shape smoke
"""

from __future__ import annotations

import argparse
import random
import textwrap
from pathlib import Path
from typing import Literal, get_args

Shape = Literal["smoke", "outputs", "chain"]

HEADER = """import marimo

__generated_with = "0.0.0"
app = marimo.App(width="medium")

with app.setup:
    import json
    import math
    from pathlib import Path

    import marimo as mo
"""

FOOTER = """

if __name__ == "__main__":
    app.run()
"""

_OUTPUTS = (
    'mo.md(f"**R{i}** passed with `{{len(_data_r{i})}}` keys")',
    "_data_r{i}",
    'mo.ui.slider(0, 100, value={i} % 100, label="R{i}")',
    'mo.ui.table([{{"id": n, "sq": n * n}} for n in range(20)])',
    'mo.accordion({{"R{i}": mo.md("details"), "raw": _data_r{i}}})',
    'mo.hstack([mo.stat({i}, label="id"), mo.stat(len(_data_r{i}), label="keys")])',
    'print("R{i}", _data_r{i})',
    "list(range({i} % 50))",
)


def _code_lines(rng: random.Random) -> int:
    # Median ~32 lines, p90 ~75, capped at 143, as in the reference notebook.
    return max(4, min(143, round(rng.lognormvariate(3.45, 0.65))))


def _markdown_cell(i: int, rng: random.Random) -> str:
    text = f"## R{i}. `feature_{i}` keeps its contract (#{10000 + i})"
    if rng.random() >= 0.7:
        paragraph = textwrap.fill(
            f"The change in #{10000 + i} added two optional parameters to "
            f"`feature_{i}` and a new `style: str | None` keyword. Both are "
            "normalized through `normalize_dimension`, and the resolved "
            "output keeps the previous shape when both are omitted.",
            width=70,
        )
        text = f"{text}\n\n{paragraph}"
    body = textwrap.indent(f'mo.md(r"""\n{text}\n""")', "    ")
    return f"@app.cell(hide_code=True)\ndef _():\n{body}\n    return\n"


def _code_body(i: int, rng: random.Random) -> list[str]:
    lines = [
        f"import inspect as _inspect_r{i}",
        "",
        f'_data_r{i} = {{"id": {i}, "name": "feature_{i}", "tags": ["a", "b"]}}',
    ]
    step = 1
    target = _code_lines(rng)
    while len(lines) < target:
        lines += [
            "",
            f"# ({step}) The value round-trips through JSON without loss.",
            f"_got_r{i}_{step} = json.loads(json.dumps(_data_r{i}))",
            f"assert _got_r{i}_{step} == _data_r{i}, _got_r{i}_{step}",
            f'assert math.isfinite(_got_r{i}_{step}["id"] + {step}), (',
            f"    _got_r{i}_{step}",
            ")",
        ]
        step += 1
    return lines


def _code_cell(i: int, shape: Shape, rng: random.Random) -> str:
    if shape == "chain":
        arg = f"v_{i - 1}" if i > 0 else ""
        value = f"v_{i - 1} + 1" if i > 0 else "0"
        return (
            f"@app.cell\ndef _({arg}):\n    v_{i} = {value}\n"
            f"    return (v_{i},)\n"
        )
    lines = _code_body(i, rng)
    if shape == "outputs":
        lines.append(_OUTPUTS[i % len(_OUTPUTS)].format(i=i))
    body = textwrap.indent("\n".join(lines), "    ")
    return f"@app.cell\ndef R{i}():\n{body}\n    return\n"


def generate(cells: int, shape: Shape = "smoke", seed: int = 0) -> str:
    """Return the source of a notebook with `cells` cells (excluding setup)."""
    rng = random.Random(seed)
    parts = [HEADER]
    for i in range(cells):
        if shape != "chain" and i % 2 == 0:
            parts.append(_markdown_cell(i // 2, rng))
        else:
            parts.append(
                _code_cell(i // 2 if shape != "chain" else i, shape, rng)
            )
    return "\n\n".join(parts) + FOOTER


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--cells", type=int, default=500)
    parser.add_argument("--shape", choices=get_args(Shape), default="smoke")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(generate(args.cells, args.shape, args.seed))


if __name__ == "__main__":
    main()
