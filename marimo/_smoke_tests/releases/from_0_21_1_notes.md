# Smoke Test Notes: 0.21.1 -> next release

Tested on: 2026-03-31
Notebook: `marimo/_smoke_tests/releases/from_0_21_1.py`

---

## Bugs

### B1. `mo.image` crashes on empty arrays

`mo.image(np.zeros((0, 0), dtype=np.uint8))` raises:

```
SystemError: tile cannot extend outside image
```

PIL's `Image.fromarray` doesn't handle zero-sized arrays. No guard exists.

**Fix:** Add an early check like `if src.size == 0: raise ValueError("Image
array must not be empty")` in `_normalize_image`.

**File:** `marimo/_plugins/stateless/image.py` (around line 59)
**Repro:** `mo.image(np.zeros((0, 0), dtype=np.uint8))`

---

### B2. `to_arrow_ipc` fallback fails on mixed-type columns

The fallback in `PandasTableManager.to_arrow_ipc()` catches the initial
feather write failure and tries `col.astype(object).infer_objects()`. But for
genuinely mixed-type columns (e.g. `[1, "two", 3.0, None]`), `infer_objects()`
still leaves it as `object` dtype and the retry raises the same
`ArrowInvalid`.

**Fix:** Add a final `astype(str)` fallback for columns that still fail after
`infer_objects()`. Confirmed: `astype(str)` lets both `pa.Array.from_pandas`
and `to_feather` succeed.

**File:** `marimo/_plugins/ui/_impl/tables/pandas_table.py:239-259`
**Repro:**
```python
from marimo._plugins.ui._impl.tables.pandas_table import PandasTableManagerFactory
import pandas as pd
factory = PandasTableManagerFactory()
mgr = factory.create()(pd.DataFrame({"mixed": [1, "two", 3.0, None]}))
mgr.to_arrow_ipc()  # ArrowInvalid
```

---

### B3. Duplicate pandas column names crash `mo.ui.table`

`mo.ui.table(pd.DataFrame([[1,2],[3,4]], columns=["a","a"]))` raises
`DuplicateError`. Pandas itself allows duplicate column names. The table
widget should either deduplicate with a suffix or give a clearer error
message.

**Repro:** `mo.ui.table(pd.DataFrame([[1,2]], columns=["a","a"]))`

---

### B4. `code_mode` `create_cell` ID collisions on large notebooks

When a notebook already has ~50 cells, `ctx.create_cell()` generates IDs that
collide with existing cells: `ValueError: Cell 'nWHF' already exists`.

**Root cause:** The `CellIdGenerator` in the code_mode context only tracks IDs
it has created during the current session (`seen_ids`). It does NOT seed itself
with existing cell IDs from the notebook. Since the generator uses a
deterministic random seed, every new ID after the initial batch collides with
cells at the same positions in the notebook.

Observed: generator `seen_ids` had 14 entries, notebook had 50 cells. All 20
test IDs collided with existing cells (100% collision rate).

**Fix:** When initializing the `CellIdGenerator` in the code_mode context,
union `seen_ids` with all existing cell IDs from the notebook.

**File:** `marimo/_code_mode/_context.py`
**Repro:** Open a notebook with 50+ cells, then `ctx.create_cell("x = 1")`.

---

## Improvements

### I1. `mo.image` silently renders garbage for NaN/inf float arrays

`mo.image(np.array([[np.nan, 1.0], [0.5, np.inf]]))` produces a
`RuntimeWarning: invalid value encountered in cast` and renders an image with
undefined pixel values. A `UserWarning` about NaN/inf in the input array would
help users catch data issues early.

---

### I2. `mo.image` silently discards imaginary part of complex arrays

`mo.image(np.array([[1+2j, 3+4j]]))` emits `ComplexWarning` but renders using
only the real part. An explicit `TypeError` or documented behavior would be
clearer.

---

### I3. `mo.image` treats 1D arrays as single-row images

`mo.image(np.array([1,2,3], dtype=np.uint8))` produces a 3x1 pixel image.
Technically correct (PIL behavior) but almost certainly not what the user
intends. Consider raising `ValueError` for 1D input, or documenting this.

---

### I4. `mo.md` passes through `<script>`, `<iframe>`, `<img onerror>`

`mo.md('<script>alert("xss")</script>')` embeds the tag verbatim in the HTML
output. This is probably by design (notebook author == trusted user), but worth
documenting. If notebooks are shared as read-only apps with user-supplied
markdown, this is a real XSS vector.

**Verified output:** `<span class="markdown prose ..."><script>alert("xss")</script></span>`

---

### I5. Empty cells collapse during ipynb conversion

`_transform_sources(["", "", ""], ...)` returns 1 cell instead of 3. Probably
intentional cleanup, but could surprise users with deliberate empty cells in
Jupyter notebooks.

---

## Edge Cases

### E1. `mo.image` — all tested edge cases

| Input | Result |
|-------|--------|
| `np.zeros((0,0), uint8)` | **CRASH** -- SystemError |
| `np.array([1,2,3], uint8)` (1D) | OK -- renders 3x1 image |
| `np.zeros((2000,2000,3), uint8)` | OK |
| `np.array([[nan, 1], [0.5, inf]])` | OK -- RuntimeWarning, garbage pixels |
| `float32` array | OK |
| `int16` array | OK |
| `bool` array | OK |
| `vmin == vmax` | OK -- zeros (black) |
| Negative vmin/vmax | OK |
| `uint8` + explicit vmin/vmax | OK -- forces renormalization |
| RGBA (4-channel) | OK |
| Shapes (1,1000), (1000,1), (1,1) | OK |
| `uint16` | OK |
| All-zeros float | OK |
| `int8` (signed) | OK |
| `float16` | OK |
| `complex` array | OK -- silently discards imaginary (ComplexWarning) |
| `list[[0,128,255],[255,128,0]]` | OK |
| `vmin > vmax` | OK -- raises ValueError |
| `vmin` only (vmax=None) | OK -- uses array max |
| `vmax` only (vmin=None) | OK -- uses array min |

---

### E2. Password sanitization

| Input | Result |
|-------|--------|
| `kind="password", value="s3cret"` | masked=True, not in HTML, Python value preserved |
| `kind="password", value=""` | masked=False (empty string is falsy) |
| `kind="password"` (no value) | masked=False |
| HTML injection `<script>` in password value | masked=True, not in HTML |
| Whitespace-only password `"   "` | masked=True |
| Unicode password `"passwort🔑"` | masked=True |
| 10k-character password | masked=True |
| `kind="text", value="visible"` | masked=False, value IS in HTML |
| `kind="email"/"url", value="test"` | masked=False |

---

### E3. Range slider validation

| Input | Result |
|-------|--------|
| `start=0, stop=100, value=[25,75]` | OK |
| `start=-100, stop=-10, value=[-80,-30]` | OK |
| `start=0.0, stop=1.0, step=0.1` | OK |
| `start=0, stop=1000000, step=1000` | OK |
| `steps=[0,100], value=[0,100]` | OK (2 steps) |
| `steps=[42], value=[42,42]` | OK (1 step, degenerate) |
| `orientation="vertical"` | OK |
| `debounce=True` | OK |
| `disabled=True` | OK |
| `value=[-5, 15]` with `stop=10` | **ValueError** -- out of bounds (correct) |
| `value=[80, 20]` (reversed) | **ValueError** -- stop > start required (correct) |

---

### E4. Data table

| Input | Result |
|-------|--------|
| Empty DataFrame | OK |
| 0-row DataFrame with columns | OK |
| NaN / None / inf values | OK |
| 100 columns | OK |
| 10k string value | OK |
| datetime / timedelta / categorical | OK |
| Unicode columns and values | OK |
| Duplicate column names | **CRASH** -- DuplicateError (see B3) |
| MultiIndex | OK (with warning) |
| Inconsistent keys (list of dicts) | OK |
| Nested dicts | OK |
| 10k rows, no pagination | OK |
| Error-raising format_mapping | OK (deferred, logs warning) |
| format_mapping on missing column | OK (ignored) |
| format_mapping returning UI element | OK |
| All selection modes | OK |
| freeze_columns | OK |
| text_justify_columns | OK |
| style_cell | OK |
| hover_template | OK |

---

### E5. Scanner (fallback static parsing)

| Input | Result |
|-------|--------|
| Syntax error in cell | OK -- 1 cell parsed |
| `@app.cell` inside string | OK -- correctly ignored (1 cell) |
| 50 cells | OK |
| Empty cells (pass/return) | OK -- 2 cells |
| Whitespace-only source | OK -- 0 cells |
| No run guard | OK -- guard=None |
| Unterminated string | OK -- 1 cell (fallback) |
| Binary junk | OK -- 0 cells |
| `hide_code=True` decorator | OK |
| `disabled=True` decorator | OK |

---

### E6. Arrow IPC (extension dtype handling)

| Input | Result |
|-------|--------|
| Normal DataFrame | OK |
| All-NaN column | OK |
| Mixed types (int+str+float+None) | **CRASH** -- ArrowInvalid (see B2) |
| Timezone-aware datetime | OK |
| Empty DataFrame | OK |
| 100k rows | OK |
| IntervalArray | OK |
| PeriodIndex | OK |
| SparseArray | OK |

---

### E7. Matplotlib

| Input | Result |
|-------|--------|
| Empty plot | OK |
| Tiny figure (0.5x0.5) | OK |
| Huge figure (50x50) | OK |
| Log-log scale | OK |
| Single subplot from 2x2 grid | OK |
| 3D projection | OK |
| 10k scatter points | OK |
| Extreme wide (20x1) | OK |

---

### E8. TOML sanitization

| Input | Result |
|-------|--------|
| Multiple keys stripped | OK, warns for each |
| Missing key path | OK -- no crash |
| Empty dict | OK |
| Deep nesting (5 levels) | OK |
| Non-dict intermediate value | OK -- returns unchanged |

---

### E9. pycache_prefix

| Input | Result |
|-------|--------|
| Absolute path + prefix set | OK -- mirrors tree under prefix |
| Relative path + prefix set | OK -- falls back to default (no mirror) |
| Directory path | OK |
| No extension (ambiguous) | OK -- treated as directory |
| Spaces in path | OK |
| Unicode in path | OK |
| Very deep path (14 levels) | OK |

---

## Additional Testing (not in notebook)

### Layout widgets
- `mo.vstack([])` (empty), nested vstack/hstack, accordion, tabs: all OK
- Callout kinds (neutral, danger, warn, success, info): all OK
- 20-deep nesting: OK
- 50-item hstack: OK
- `mo.tree` with nested dicts: OK

### Form/Batch/Dictionary
- `mo.ui.dictionary`, `mo.ui.array` (incl. empty): all OK
- Nested dictionaries: OK
- `mo.ui.form` with options: OK
- `mo.md(...).batch(...)`: OK

### State
- `mo.state(0)`, `mo.state(None)`, `mo.state({...})`: all OK
- `allow_self_loops=True`: OK

### Status/Display
- `mo.status.progress_bar`: OK
- `mo.status.spinner`: OK
- `mo.plain` with int, str, list, dict: all OK
- `mo.as_html`: OK
- `mo.stop(False, ...)`: OK (no stop)

### Dataframe explorer
- Basic, 10k rows, all-NaN, single column, format_mapping: all OK

### Lint config
- `resolve_lint_config(None, None)`: returns None (no config)
- `resolve_lint_config("MB,MR001", None)`: selects those rules
- `resolve_lint_config(None, "MF004,MF007")`: ignores those rules
- Both select + ignore: OK

### Path utilities
- `normalize_path`: preserves symlinks, handles absolute/relative correctly
- `is_cloudpath`: returns False for standard paths
