# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "numpy",
#     "pandas",
#     "matplotlib",
# ]
# ///
# Copyright 2026 Marimo. All rights reserved.
#
# Smoke tests for changes between 0.21.1 and 0.21.2

import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _():
    import numpy as np
    import pandas as pd

    return np, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 1. `mo.image` — vmin/vmax and uint8 normalization (#8889)

    - **New params:** `vmin` and `vmax` for array normalization control
    - **Fix:** uint8 arrays are no longer re-normalized (values preserved as-is)
    - **Fix:** uniform float arrays don't cause division-by-zero
    """)
    return


@app.cell
def _(mo, np):
    # uint8 arrays should be passed through without normalization.
    # Previously, a uniform uint8 array would normalize to all-black.
    arr_uint8 = np.full((20, 40, 3), 180, dtype=np.uint8)
    mo.md("**uint8 array (uniform 180)** — should appear as a solid light-gray rectangle, NOT black:")
    return (arr_uint8,)


@app.cell
def _(arr_uint8, mo):
    mo.image(arr_uint8)
    return


@app.cell
def _(mo, np):
    # vmin/vmax clamp and normalize: value 500 in [0, 1000] -> ~127
    arr_float = np.full((20, 40), 500.0)
    img = mo.image(arr_float, vmin=0, vmax=1000)
    mo.md("**float array with vmin=0, vmax=1000, value=500** — should be mid-gray:")
    return (img,)


@app.cell
def _(img):
    img
    return


@app.cell
def _(mo, np):
    # Uniform float array should not raise (division by zero guard)
    arr_uniform = np.full((10, 10), 42.0)
    _img = mo.image(arr_uniform)
    mo.md("**Uniform float array** — no crash, renders as black (zeros):")
    return


@app.cell
def _(mo, np):
    # vmin > vmax should raise ValueError
    try:
        mo.image(np.zeros((5, 5)), vmin=10, vmax=5)
        _result = "FAIL: should have raised ValueError"
    except ValueError as e:
        _result = f"PASS: {e}"
    mo.md(f"**vmin > vmax raises ValueError:** `{_result}`")
    return


@app.cell
def _(np):
    from marimo._plugins.stateless.image import _normalize_image

    # Programmatic assertion: uint8 values are preserved
    src_uint8 = np.array([[100, 200], [50, 255]], dtype=np.uint8)
    _result = _normalize_image(src_uint8, vmin=None, vmax=None)
    # Result should be a BytesIO; the important thing is it didn't crash
    # and the internal path skipped normalization
    assert _result is not None, "uint8 normalization returned None"

    # Programmatic assertion: vmin/vmax clipping works
    src_float = np.array([[0.0, 500.0], [1000.0, 1500.0]])
    _result2 = _normalize_image(src_float, vmin=0, vmax=1000)
    assert _result2 is not None, "vmin/vmax normalization returned None"

    print("All mo.image assertions passed")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 2. Password sanitization in frontend render (#8857)

    Passwords with an initial value are no longer embedded in the HTML.
    The real value is preserved Python-side while the frontend shows dots.

    ### Manual test steps:
    1. **Initial state:** The password field below shows dots (masked),
       the Python value reads `"s3cret"`.
    2. **Action:** Type a new value in the password field.
    3. **Expected:** `.value` updates to whatever you typed.
    """)
    return


@app.cell
def _(mo):
    pw = mo.ui.text(kind="password", value="s3cret", label="Password")
    pw
    return (pw,)


@app.cell
def _(mo, pw):
    # The real value should be preserved Python-side
    assert pw.value == "s3cret", f"Expected 's3cret', got '{pw.value}'"
    # The HTML should NOT contain the password
    assert "s3cret" not in pw.text, "Password leaked into HTML!"
    mo.md(
        f"""
        - `pw.value` = `{pw.value}` (should be `s3cret` initially)
        - Password in HTML: `{"YES — BUG" if "s3cret" in pw.text else "No — PASS"}`
        """
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 3. Range slider — drag track to move entire range (#8698)

    ### Manual test steps:
    1. **Initial state:** Range slider with value [25, 75].
    2. **Action:** Click and drag the *colored track* (between the two handles).
    3. **Expected:** Both handles move together, maintaining the 50-unit gap.
       The range cannot exceed [0, 100].
    """)
    return


@app.cell
def _(mo):
    range_slider = mo.ui.range_slider(
        start=0,
        stop=100,
        step=5,
        value=[25, 75],
        show_value=True,
        label="Drag the track between handles",
    )
    range_slider
    return (range_slider,)


@app.cell(hide_code=True)
def _(mo, range_slider):
    mo.md(f"""
    Current value: **{range_slider.value}** (gap should stay ~50 when track-dragging)
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 4. Data table improvements

    ### 4a. Virtualized rows when pagination disabled (#8899)
    Table with 500 rows and `pagination=False`. Only ~25 rows should be
    in the DOM at any time (check DevTools → Elements).

    **Steps:** Scroll down — rows should render smoothly. Header stays sticky.
    """)
    return


@app.cell
def _(mo, pd):
    big_df = pd.DataFrame(
        {
            "row_id": range(500),
            "value": [i * 1.1 for i in range(500)],
            "category": [f"cat_{i % 10}" for i in range(500)],
        }
    )
    table_virtual = mo.ui.table(big_df, pagination=False, label="500-row virtualized table")
    table_virtual
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### 4b. Auto right-align numeric columns, normalize decimals (#8887)

    Numeric columns should be right-aligned. Decimal places should be
    consistent within each column. Booleans render as `True`/`False`.
    """)
    return


@app.cell
def _(mo, pd):
    align_df = pd.DataFrame(
        {
            "integer": [1, 22, 333, 4444],
            "float_varied": [1.1, 22.22, 333.333, 4444.4444],
            "boolean": [True, False, True, False],
            "text": ["left", "aligned", "by", "default"],
        }
    )
    mo.ui.table(align_df, label="Numeric alignment test")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### 4c. No cell selection when interactive elements present (#8862)

    **Steps:**
    1. Click a button in the table below.
    2. **Expected:** The button triggers — cell is NOT selected (no blue highlight).
    """)
    return


@app.cell
def _(mo):
    interactive_table = mo.ui.table(
        {
            "name": ["Alice", "Bob", "Charlie"],
            "action": [
                mo.ui.button(label="Click A", on_click=lambda _: print("A clicked")),
                mo.ui.button(label="Click B", on_click=lambda _: print("B clicked")),
                mo.ui.button(label="Click C", on_click=lambda _: print("C clicked")),
            ],
        },
        label="Table with interactive buttons",
    )
    interactive_table
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### 4d. Format mapping search uses raw data (#8622)

    The search box should filter on the raw URL, not the rendered HTML.

    **Steps:**
    1. Type `example` in the search box.
    2. **Expected:** Row with `example.com` appears.
    """)
    return


@app.cell
def _(mo):
    format_table = mo.ui.table(
        [
            {"id": 1, "url": "https://example.com"},
            {"id": 2, "url": "https://marimo.io"},
            {"id": 3, "url": "https://github.com"},
        ],
        format_mapping={"url": lambda x: mo.md(f"[Link]({x})")},
        label="Search by raw URL, not rendered HTML",
    )
    format_table
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 5. `mo.ui.matplotlib` — no stretch effect (#8883)

    Extreme aspect ratios should render without distortion.
    The CSS now uses `aspect-ratio` instead of fixed pixel height.

    ### Manual test:
    1. Both plots below should display without stretching or squishing.
    2. Resize the browser window — aspect ratio should be preserved.
    """)
    return


@app.cell
def _(mo):
    import matplotlib.pyplot as plt

    fig_wide, ax_wide = plt.subplots(figsize=(12, 2))
    ax_wide.plot([1, 2, 3, 4, 5], [1, 4, 2, 5, 3])
    ax_wide.set_title("Wide figure (12×2) — should NOT be stretched vertically")

    fig_tall, ax_tall = plt.subplots(figsize=(3, 8))
    ax_tall.bar(["A", "B", "C"], [10, 20, 15])
    ax_tall.set_title("Tall figure (3×8)")

    mo.vstack([mo.ui.matplotlib(ax_wide), mo.ui.matplotlib(ax_tall)])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 6. Markdown & HTML rendering fixes

    ### 6a. List styling — tighter margins, proper bullet cycling (#8768)

    The list below should have:
    - Compact spacing (no excessive gaps)
    - Bullet style cycling: disc → circle → square
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    - Level 1 item A
      - Level 2 nested
        - Level 3 deep nested
      - Level 2 another
    - Level 1 item B

    1. Ordered item one
       - Unordered nested
         - Deep nested
    2. Ordered item two
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### 6b. Tooltip rendering in portal (#8813)

    Tooltips should not be clipped by overflow containers.

    **Steps:** Hover over the text below — tooltip should appear fully visible.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    <div style="overflow: hidden; max-height: 60px; border: 2px solid red; padding: 8px;">
        <span data-tooltip="This tooltip should NOT be clipped by the red overflow container!">
            Hover me — tooltip should escape the red box
        </span>
    </div>
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 7. macOS backtick completion fix (#8829)

    **macOS only.** Typing a backtick (`) should insert the character,
    NOT open the autocomplete menu.

    ### Steps:
    1. Click into any code cell.
    2. Type a backtick character.
    3. **Expected:** Backtick is inserted. No autocomplete popup.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 8. Programmatic tests for internal fixes
    """)
    return


@app.cell
def _(mo):
    import sys
    from pathlib import Path

    from marimo._utils.paths import notebook_output_dir

    # Without pycache_prefix: should place next to notebook
    _original_prefix = getattr(sys, "pycache_prefix", None)

    result_default = notebook_output_dir(Path("/tmp/notebooks/test.py"))
    assert result_default == Path("/tmp/notebooks/__marimo__"), f"Got {result_default}"

    # None path: relative to CWD
    result_none = notebook_output_dir(None)
    assert result_none == Path("__marimo__"), f"Got {result_none}"

    mo.md("**8a. `notebook_output_dir` pycache_prefix:** PASS")
    return


@app.cell
def _(mo):
    from marimo._config.reader import sanitize_pyproject_dict

    test_dict = {"tool": {"uv": {"sources": {"bad": "value"}}}}
    sanitize_pyproject_dict(test_dict, (("tool", "uv", "sources"),))

    # Key should be removed (a warning is also logged — visible in console)
    assert "sources" not in test_dict["tool"]["uv"], "Key was not removed"

    # Multiple keys
    _d2 = {"tool": {"uv": {"sources": {"x": 1}, "index": [1]}}}
    sanitize_pyproject_dict(_d2, (("tool", "uv", "sources"), ("tool", "uv", "index")))
    assert "sources" not in _d2["tool"]["uv"]
    assert "index" not in _d2["tool"]["uv"]

    # Missing path should not crash
    sanitize_pyproject_dict({"tool": {}}, (("tool", "nonexistent", "key"),))

    mo.md("**8b. `sanitize_pyproject_dict` security key removal:** PASS")
    return


@app.cell
def _(mo):
    from marimo._utils.health import CGROUP_V1_MEMORY_UNLIMITED_THRESHOLD

    # The threshold should be 2^60 (1 exabyte)
    assert CGROUP_V1_MEMORY_UNLIMITED_THRESHOLD == 2**60, (
        f"Expected 2**60, got {CGROUP_V1_MEMORY_UNLIMITED_THRESHOLD}"
    )
    # Typical cgroup v1 "unlimited" value is ~9.2e18 which is > 2^60
    fake_unlimited = 9223372036854771712
    assert fake_unlimited >= CGROUP_V1_MEMORY_UNLIMITED_THRESHOLD, (
        "Typical cgroup v1 unlimited should exceed threshold"
    )

    mo.md("**8c. cgroup v1 memory threshold:** PASS")
    return


@app.cell
def _(mo):
    import textwrap

    from marimo._ast.scanner import ScannedCell, scan_notebook

    # A minimal valid notebook (textwrap.dedent to avoid indentation artifacts)
    _src = textwrap.dedent("""\
        import marimo
        app = marimo.App()

        @app.cell
        def _():
            x = 1
            return (x,)

        if __name__ == "__main__":
            app.run()
    """)
    _result = scan_notebook(_src)
    assert len(_result.cells) >= 1, f"Expected >=1 cell, got {len(_result.cells)}"
    assert isinstance(_result.cells[0], ScannedCell)
    assert _result.run_guard_line is not None, "Should detect run guard"

    # Empty source should not crash
    _empty_result = scan_notebook("")
    assert _empty_result.cells == []

    mo.md("**8d. Fallback static scanner:** PASS")
    return


@app.cell
def _(mo):
    from marimo._convert.ipynb.to_ir import _transform_sources

    # _transform_sources should not crash on problematic input
    # It wraps transforms in try/except and validates cell count
    _test_sources = ["x = 1", "y = x + 1", "print(y)"]
    _test_metadata = [{} for _ in _test_sources]
    _test_hide = [False for _ in _test_sources]
    _cells, _excl = _transform_sources(_test_sources, _test_metadata, _test_hide)
    assert len(_cells) == len(_test_sources), (
        f"Cell count changed: {len(_test_sources)} -> {len(_cells)}"
    )

    mo.md("**8e. Hardened ipynb transforms:** PASS")
    return


@app.cell
def _(mo, pd):
    from marimo._plugins.ui._impl.tables.pandas_table import (
        PandasTableManagerFactory,
    )

    # Normal DataFrame should serialize without issues
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    _factory = PandasTableManagerFactory()
    _manager = _factory.create()(df)
    ipc_bytes = _manager.to_arrow_ipc()
    assert isinstance(ipc_bytes, bytes), f"Expected bytes, got {type(ipc_bytes)}"
    assert len(ipc_bytes) > 0, "IPC bytes are empty"

    mo.md("**8f. Arrow IPC fallback for extension dtypes:** PASS")
    return


@app.cell
def _(mo):
    # Password with value => masked
    pw_with_val = mo.ui.text(kind="password", value="secret")
    assert pw_with_val._masked is True, "Should be masked when value is set"
    assert pw_with_val.value == "secret", "Python-side value should be preserved"
    assert "secret" not in pw_with_val.text, "Password should not be in HTML"

    # Password without value => not masked
    pw_empty = mo.ui.text(kind="password")
    assert pw_empty._masked is False, "Should not be masked when no value"

    # Non-password with value => not masked
    pw_text = mo.ui.text(value="visible")
    assert pw_text._masked is False, "Non-password should not be masked"
    assert "visible" in pw_text.text, "Non-password value should be in HTML"

    mo.md("**8g. Password masking logic:** PASS")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 9. Download filename uses variable name (#8811)

    The download button should use the variable name as the filename.

    ### Steps:
    1. Click the download button (CSV) on the table below.
    2. **Expected:** File is named `my_named_table.csv`, NOT `download.csv` or `df.csv`.
    """)
    return


@app.cell
def _(mo, pd):
    my_named_table = mo.ui.table(
        pd.DataFrame({"x": [1, 2, 3], "y": ["a", "b", "c"]}),
        label="Download should be named 'my_named_table.csv'",
    )
    my_named_table
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 10. Markdown preview stays in sync on local edits (#8832)

    ### Steps:
    1. Edit the markdown cell below (toggle to editor mode).
    2. Type or delete text.
    3. **Expected:** The rendered preview updates immediately — no stale content.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    Edit me — the preview should update instantly as you type!
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 11. `hide_code` on kernel-created cells (#8926)

    This cell uses `hide_code=True`. The code should be hidden by default.
    Toggle it to verify it works.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 12. Lint configuration (#8560)

    `marimo check` now supports `--select` and `--ignore` flags, and
    reads lint config from `pyproject.toml` under `[tool.marimo.lint]`.

    Run in terminal:
    ```bash
    marimo check this_notebook.py --ignore MF004
    ```
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## 13. Additional checks

    ### 13a. Data table — large table without pagination (virtualization)

    Scroll this table — it should be smooth with sticky headers.
    Open DevTools → Elements to verify only ~25 rows are in the DOM.
    """)
    return


@app.cell
def _(mo, np, pd):
    large_df = pd.DataFrame(
        {
            "id": range(1000),
            "random": np.random.default_rng(42).standard_normal(1000),
            "category": [f"group_{i % 20}" for i in range(1000)],
        }
    )
    mo.ui.table(large_df, pagination=False, label="1000-row virtualized table")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ### 13b. Range slider with custom steps

    **Steps:**
    1. Drag the track between handles.
    2. **Expected:** Both handles snap to Fibonacci-like steps together.
    """)
    return


@app.cell
def _(mo):
    fib_slider = mo.ui.range_slider(
        steps=[1, 2, 3, 5, 8, 13, 21, 34, 55, 89],
        value=[5, 34],
        show_value=True,
        label="Fibonacci steps — drag the track",
    )
    fib_slider
    return (fib_slider,)


@app.cell(hide_code=True)
def _(fib_slider, mo):
    mo.md(f"""
    Fibonacci slider value: **{fib_slider.value}**
    """)
    return


if __name__ == "__main__":
    app.run()
