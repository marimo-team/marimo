from typing import Any, Tuple

import marimo

__generated_with = "0.1.0"
app = marimo.App()


@app.cell
def one() -> Tuple[Any]:
    x = 0
    return x,


@app.cell
def two(x: Any) -> Tuple[Any, Any]:
    y = x + 1
    z = y + 1
    'z'
    return y, z


@app.cell
def three(x: Any, y: Any) -> Tuple[Any]:
    a = x + y
    return a,


if __name__ == "__main__":
    app.run()
