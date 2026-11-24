# Backend load/save (file ↔ app) — large-notebook performance

Scope: everything that happens to a notebook *file* before/after the kernel
runs code: parse, per-cell compile, graph build, codegen/save, reload, the
whole-notebook CLI commands, and process startup.

## Measurements

**How to read the numbers.** The machine was shared with five other
benchmarks for the whole session (load average 100–360 on 14 cores), so:

- *Run 1* of the load benchmark happened before the load ramped up and is
  **wall-clock** (`time.perf_counter`, median of 5). It is the best absolute
  reference I have.
- Everything else is **CPU time of the process** (`time.process_time`, median
  of 5–7), which under this contention reads about 1.5–2× the calm value
  (e.g. `ast.parse` of `smoke-500.py`: 37 ms calm, 52–70 ms contended).
- Before/after numbers are **interleaved A/B in one process**
  (`bench_prototypes.py`), so the *ratios* are the reliable part.
- CLI numbers are user+sys CPU of the child process tree.
- The committed test counts Python function calls, which is deterministic.

All scripts are in `.context/perf/backend-load-save/`; raw output is next to
them (`*_results*.txt`, `prof/*.prof`).

### M1. File → `App` stages (`bench_load.py`, run 1, wall ms, median of 5)

| `smoke` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope 250→2000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| read file | 0.1 | 0.1 | 0.1 | 0.1 | 0.3 | 0.2 | – |
| reference: `ast.parse(file)` | 3.0 | 5.8 | 15.8 | 37.3 | 78.8 | 178 | 1.16 |
| `parse_notebook` | 16.8 | 30.7 | 84.3 | 182 | 396 | 1042 | 1.21 |
| `load_notebook_ir` (compile + register) | 18.0 | 32.1 | 83.1 | 181 | 398 | 914 | 1.15 |
| `load_app` = both | 34.5 | 63.6 | 172 | 388 | 822 | 1939 | 1.16 |
| `AppFileManager(path)` | 34.7 | 64.0 | 168 | 387 | 830 | 1903 | 1.17 |

| `outputs` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `parse_notebook` | 17.7 | 33.4 | 89.5 | 205 | 431 | 1127 | 1.22 |
| `load_notebook_ir` | 20.7 | 40.7 | 97.4 | 234 | 499 | 1084 | 1.16 |
| `load_app` | 37.5 | 71.3 | 192 | 432 | 927 | 2483 | 1.23 |

| `chain` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference: `ast.parse(file)` | 0.4 | 1.0 | 2.7 | 5.3 | 10.8 | 21.5 | 0.99 |
| `parse_notebook` | 2.7 | 5.1 | 13.7 | 27.9 | 50.3 | 98.9 | 0.95 |
| `load_notebook_ir` | 2.9 | 5.4 | 15.7 | 31.5 | 61.3 | 196 | 1.21 |
| `load_app` | 6.2 | 12.1 | 29.7 | 56.8 | 111 | 257 | 1.04 |

`parse_notebook` costs **4.9×** a plain `ast.parse` of the same file, and
`load_app` **10.4×** (smoke-500). Nothing here is quadratic for the
smoke/outputs shapes; the 1.15–1.2 exponent is the garbage collector (F11).

Graph build (`App._maybe_initialize`, first `InternalApp.graph` access), timed
directly (`bench_load.py` run 2, CPU ms, median of 5, contended):

| graph build | 50 | 100 | 250 | 500 | 1000 | 2000 | slope 250→2000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `smoke` (star: every cell depends on setup) | 0.6 | 1.4 | 6.9 | 22 | 81 | 271 | **1.77** |
| `outputs` (star) | 0.7 | 2.0 | 8.1 | 24 | 115 | 393 | **1.86** |
| `chain` | 2.7 | 5.1 | 30 | 135 | 509 | 2431 | **2.11** |

For comparison, the same run measured `load_app` at 797 ms (smoke-500) and
85 ms (chain-500): on a 500-cell chain the graph build costs more than
parsing and compiling the notebook, and at 2000 cells 5.9× more. Calm run 1
had 80 ms (chain-500) and 1.28 s (chain-2000) for the same step.

### M2. Where one `compile_cell` goes (`bench_compile.py`, CPU ms, median of 7, contended)

| step (per 501 cells) | smoke-500 | outputs-500 | chain-500 |
| --- | --- | --- | --- |
| `load_notebook_ir` total | 561 | 668 | 115 |
| `compile_cell` total | 508 (91%) | 630 (94%) | 86 (75%) |
| AST parse, **twice per cell** (`module_compile`) | 175 | 149 | 19 |
| `ScopedVisitor.visit` (defs/refs) | 169 | 165 | 20 |
| bytecode, twice per cell (body + last expr) | 81 | 63 | 16 |
| `ends_with_semicolon` (tokenizes the cell) | 9 | **78** | 0 |
| `NotebookDocument.apply` (one transaction per cell) | 19 | 18 | 12 |
| `CellImpl.configure` / `CellImpl()` / linecache / cell ids | 24 | 25 | 13 |

Calm run 1 gave 182 ms for the same 501 `compile_cell` calls (0.36 ms/cell).

### M3. Whole-notebook passes when a notebook is opened

`marimo edit smoke-500.py --headless`, one session opened by
`scripts/benchmarks/ws_traffic.py --expect-run`, calls counted in every process
by an import hook (`hook/sitecustomize.py`, `run_session.sh`,
`summarize_counts.py`). Times are contended wall ms inside the function.

| process | function | calls | ms | called from |
| --- | --- | --- | --- | --- |
| server | `parse_notebook` | 1 | 620 | `check_app_correctness` → `get_notebook_status` (CLI pre-flight) |
| server | `load_app` (parse + compile all) | 1 | ~1060 | `AppFileManager.__init__` ← `workspace.load` ← `app_manager` ← index page |
| server | `load_app` | 1 | ~1060 | `AppFileManager.__init__` ← `workspace.load` ← `_create_session` |
| server | `load_app` | 1 | 1139 | `AppFileManager.__init__` ← `SessionBridge._file_manager` ← `_read` |
| server | `compile_cell` | 501 | 1432 | `CellAnalyzer.__call__` (worker thread) |
| server | `code_fingerprint` | 4 × 501 | 1261 | `DocumentCell.__post_init__` ← `sources` ×2, `from_file_manager`, `instantiate` |
| kernel | `compile_cell` | 501 | 426 | `_handle_markdown_cells_on_instantiate` |

Totals: the file is parsed **4×**, every cell is compiled **5×** (4× in the
server process, which never executes a cell) and fingerprinted **4×**. The
same counts at 100 cells (`smoke-100`): 4 / 5 / 4.

### M4. Save stages (`bench_save.py`, CPU ms, median of 5, contended)

| `smoke` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope 250→2000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference: `ast.parse(file)` | 3.5 | 7.4 | 19.9 | 57.2 | 127 | 198 | 1.11 |
| `copy.deepcopy(document.cells)` | 0.2 | 0.3 | 0.7 | 1.8 | 3.4 | 5.6 | 0.99 |
| `cells_to_ir` | 0.1 | 0.1 | 0.2 | 0.4 | 1.0 | 1.6 | 0.94 |
| `generate_filecontents_from_ir` | 22.2 | 51.5 | 127 | 247 | 667 | 1257 | 1.10 |
| `save_from_cells`, one cell edited | 33.1 | 49.1 | 127 | 302 | 587 | 1164 | 1.06 |
| `save_from_cells`, nothing changed | 28.1 | 49.6 | 122 | 293 | 524 | 1242 | 1.12 |
| host etag `Document(sources(cells))` | 9.7 | 13.6 | 41.4 | 79.8 | 147 | 272 | 0.91 |
| `bridge.save` = deepcopy + save + 2 × etag | 52.7 | 76.6 | 211 | **463** | 884 | 1714 | 1.01 |
| … in units of `ast.parse(file)` | 15 | 10 | 11 | **8.1** | 7.0 | 8.6 | – |

| `chain` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope 250→2000 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| reference: `ast.parse(file)` | 0.9 | 1.9 | 4.1 | 10.9 | 18.4 | 41.2 | 1.11 |
| `generate_filecontents_from_ir` | 6.5 | 12.1 | 40.3 | 77.3 | 211 | 776 | **1.42** |
| `save_from_cells`, one cell edited | 10.1 | 13.5 | 46.9 | 80.9 | 257 | 790 | **1.36** |
| host etag `Document(sources(cells))` | 1.5 | 2.7 | 8.4 | 13.0 | 26.5 | 50.4 | 0.86 |
| `bridge.save` = deepcopy + save + 2 × etag | 13.6 | 19.4 | 64.7 | 109 | 314 | 900 | 1.27 |
| … in units of `ast.parse(file)` | 14 | 10 | 16 | 10 | 17 | 22 | – |

`outputs-500`: codegen 441, save 504, etag 183, `bridge.save` 871 ms
(12.5 × `ast.parse(file)`); its 1000/2000 columns were hit by a contention
spike in this run (run 1 gave slope 1.18 for codegen and 1.09 for the save).

In calm terms a save of the 500-cell smoke notebook is ≈8 whole-file parses,
i.e. ≈0.3 s of CPU (8.1 × 37 ms), whether or not anything changed.

One save of smoke-500 with one edited cell, attributed (`bench_save.py`,
inclusive CPU ms, mean of 3 saves; run 1 was under heavier contention than
run 2):

| function | run 1 | run 2 | calls |
| --- | --- | --- | --- |
| `generate_filecontents` | 574 | 395 | 1 |
| → `compile_cell` (every cell, via `TopLevelStatus.update`) | 463 | 323 | 500 |
| → `safe_serialize_cell` | 93 | 61 | 500 |
| →→ defensive `ast_parse` of each generated cell | 56 | 40 | 501 |
| →→ `format_markdown` (tokenize) | 17 | 10 | 250 |
| `content_matches_last_save` (regex over old + new text) | 12 | 11 | 1 |
| `storage.write` | 1.4 | 0.6 | 1 |
| `get_header_comments` (re-read file) | 0.8 | 0.3 | 1 |
| `notebook_file_lock` | 0.06 | 0.01 | 1 |

In both runs `compile_cell` is 81–82% of codegen and the re-parse 10%.

### M5. Prototype fixes, before → after (`bench_prototypes.py`, CPU ms, median of 7, interleaved A/B, outputs asserted identical)

| prototype (monkeypatched, `prototypes.py`) | smoke-500 | smoke-2000 | outputs-500 | chain-500 | chain-2000 |
| --- | --- | --- | --- | --- | --- |
| `parse_notebook`: `fixed_dedent` fast paths (exact) | 282 → 129 (2.2×) | 1331 → 572 (2.3×) | 323 → 143 (2.3×) | 43 → 23 (1.9×) | 157 → 91 (1.7×) |
| … + skip tokenize when no multi-line token possible | 278 → 100 (2.8×) | 1245 → 428 (2.9×) | 332 → 124 (2.7×) | 39 → 20 (2.0×) | 158 → 76 (2.1×) |
| … no tokenize at all (upper bound, *not* equivalent) | 294 → 87 (3.4×) | 1275 → 375 (3.4×) | 327 → 93 (3.5×) | 38 → 17 (2.2×) | 157 → 73 (2.2×) |
| `load_notebook_ir`: `";" in code` before tokenizing | 295 → 282 | 1321 → 1298 | 390 → 335 (1.2×) | 44 → 42 | 243 → 248 |
| save, 1 cell edited: codegen compile cache | 308 → 59 (5.2×) | 1887 → 271 (7.0×) | 436 → 81 (5.4×) | 67 → 40 (1.7×) | 503 → 397 (1.3×) |
| … + skip re-parse of already-validated cells | 338 → 22 (15×) | 1996 → 84 (24×) | 389 → 20 (19×) | 71 → 32 (2.2×) | 448 → 317 (1.4×) |
| … + `sql_defs` from the cell's own defs | 318 → 21 (15×) | 1897 → 78 (24×) | 387 → 22 (18×) | 70 → 14 (4.9×) | 453 → 44 (10×) |
| codegen alone: `sql_defs` fix only | 296 → 293 | 1887 → 1859 | 376 → 376 | 63 → 45 (1.4×) | 451 → 181 (2.5×) |
| host etag `Document(sources(cells))`: fingerprint LRU | 84 → 3.3 (26×) | 419 → 16 (27×) | 132 → 3.9 (34×) | 11 → 2.7 (4.1×) | 46 → 11 (4.0×) |
| `NotebookDocument`: n transactions → one batch | 3.9 → 0.3 (12×) | 80 → 1.6 (49×) | – | 4.4 → 0.4 (13×) | 77 → 1.7 (46×) |
| `document.get_cell` for every cell: scan → id index | 2.2 → 0.1 (15×) | 47 → 0.5 (90×) | – | 2.2 → 0.1 (22×) | 45 → 0.4 (123×) |

Graph build (`App._maybe_initialize`), same method
(`prototype_graph_results.txt`):

| prototype | smoke-500 | smoke-2000 | outputs-2000 | chain-500 | chain-2000 |
| --- | --- | --- | --- | --- | --- |
| one ancestor pass after bulk registration | 27 → 26 | 288 → 291 | 543 → 551 | 166 → 18 (9.2×) | 2877 → 214 (13×) |
| name → referring/deleting cells index | 19 → 7.9 (2.4×) | 260 → 31 (8.3×) | 802 → 62 (13×) | 151 → 133 | 2733 → 2408 |
| `induced_subgraph` set membership | 23 → 26 | 290 → 304 | 610 → 610 | 163 → 164 | 2670 → 2635 |
| all three | 21 → 4.9 (4.4×) | 298 → 20 (15×) | 710 → 30 (24×) | 163 → 6.4 (26×) | 2674 → 25 (106×) |

Reversed chain (every cell uses a variable defined by the cell *below* it),
with the three fixes above already applied:

| | chain-500 | chain-1000 | chain-2000 |
| --- | --- | --- | --- |
| graph build, of which `detect_cycle_for_edge` | 73, 66 | 420, 402 | 2811, 2756 |
| with predecessor-map BFS in `get_path` | 67 → 25 | 402 → 111 | 3164 → 762 (4.2×) |

The behaviour-preserving prototypes were also run under the repo's tests
(`pytest -p pytest_plugin`, scratch venv): `tests/_ast/{test_dedent,test_parse,
test_load,test_codegen,test_compiler,test_cell_manager,test_toplevel,test_app}.py`,
`tests/_runtime/test_dataflow.py`, `tests/_core`, `tests/_session/notebook`,
`tests/_server/host` → 1684 passed, 20 skipped; with the graph index and
predecessor-BFS prototypes added, `tests/_runtime/{test_dataflow,
test_dataflow_cases,test_topology,test_scheduler}.py` and
`tests/_server/host/test_host_analysis.py` → 191 passed. The bulk ancestor
pass is not in that set (it changes behaviour, see F5). The patch *files* in
`../patches/backend-load-save-*.patch` were validated separately,
by importing the patched copies through a meta-path finder
(`pytest -p patched_plugin`): `tests/_ast`, `tests/_utils`, `tests/_core`,
`tests/_convert`, `tests/_session/notebook`, `tests/_lint`,
`tests/_runtime/{test_dataflow,test_dataflow_cases,test_topology,test_scheduler,test_runtime}.py`,
`tests/_server/host/{test_host_analysis,test_host_document}.py` →
3380 passed, 88 skipped, 4 failed. All 4 also fail on the unmodified tree in
the same scratch venv (2× `tests/_lint/test_host_protocol_codegen.py`,
`test_inline_script_metadata.py::test_get_dependencies_github` needs network,
`test_cell.py::test_async_cell_notebook_location[False]` resolves a path into
another investigator's `.context/perf/backend-runtime/overlay`).
`tests/_lint/test_host_protocol_documents.py` does not collect in that venv
and was skipped.

### M6. File-watch reload (`bench_reload.py`, `AppFileManager.reload()`, CPU ms, contended)

| notebook | cells changed on disk | reload | `load_app` | `match_cell_ids_by_similarity` | `similarity_score` calls |
| --- | --- | --- | --- | --- | --- |
| smoke-500 | 1 | 763 | 755 | 0.8 | 1 |
| smoke-500 | 50 | 796 | 781 | 7.5 | 2,500 |
| smoke-500 | 500 | 1580 | 668 | 896 | 250,000 |
| chain-500 | 500 | 662 | 100 | 552 | 250,000 |
| chain-1000 | 1 | 239 | 232 | 1.9 | 1 |
| chain-1000 | 1000 | 2640 | 277 | 2317 | 1,000,000 |

### M7. CLI commands (`bench_cli.py`, CPU seconds, median of 3, contended)

Startup baseline: `python -c pass` 0.02 s, `python -c "import marimo"` 0.57 s,
`marimo --version` 0.81 s.

`slope` is the 250→2000 exponent after subtracting startup (0.81 s for
`marimo …`, 0.57 s for `python …`); `ms/cell` is the same at 500 cells.

| `smoke` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope | ms/cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `marimo check` | 1.02 | 1.17 | 1.70 | 2.47 | 3.82 | 8.02 | 1.01 | 3.3 |
| `marimo export script` | 0.89 | 0.94 | 1.20 | 1.54 | 2.10 | 3.66 | 0.96 | 1.5 |
| `marimo export ipynb` | 1.08 | 0.99 | 1.37 | 1.54 | 2.32 | 4.43 | 0.89 | 1.5 |
| `marimo export html` | 2.24 | 2.53 | 3.35 | 3.65 | 5.62 | 12.49 | 0.73 | 5.7 |
| `python notebook.py` | 1.01 | 1.11 | 1.45 | 1.88 | 3.00 | 5.61 | 0.84 | 2.6 |

| `outputs` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope | ms/cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `marimo check` | 1.15 | 1.31 | 2.30 | 3.82 | 4.69 | 11.56 | 0.95 | 6.0 |
| `marimo export script` | 0.85 | 1.11 | 1.59 | 1.98 | 2.67 | 6.11 | 0.92 | 2.3 |
| `marimo export ipynb` | 0.98 | 1.23 | 1.60 | 2.02 | 2.97 | 7.56 | 1.03 | 2.4 |
| `marimo export html` | 2.06 | 2.70 | 4.31 | 5.10 | 9.10 | 17.00 | 0.74 | 8.6 |
| `python notebook.py` | 1.03 | 1.31 | 2.07 | 2.40 | 3.97 | 9.54 | 0.86 | 3.7 |

| `chain` | 50 | 100 | 250 | 500 | 1000 | 2000 | slope | ms/cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `marimo check` | 1.14 | 1.27 | 1.32 | 1.61 | 2.38 | 4.31 | 0.93 | 1.6 |
| `marimo export script` | 1.06 | 1.09 | 1.10 | 1.60 | 2.42 | **6.52** | **1.44** | 1.6 |
| `marimo export ipynb` | 1.17 | 1.25 | 1.29 | 1.79 | 2.59 | 4.40 | 0.97 | 2.0 |
| `marimo export html` | 2.60 | 2.48 | 3.70 | 5.85 | 7.24 | **20.65** | 0.93 | 10.1 |
| `python notebook.py` | 1.04 | 1.08 | 1.28 | 1.58 | 2.39 | **9.46** | **1.22** | 2.0 |

`export ipynb` ran from the scratch venv because `.venv` has no `nbformat`.
The chain notebooks are one line per cell (140 KB at 2000 cells vs 1.7 MB for
smoke-2000), yet at 2000 cells `export script`, `export html` and script mode
cost more than on smoke: 1000 → 2000 cells is 2.7×, 2.9× and 4.0×.

Profiles (`cProfile`, `prof/*.prof`, smoke-2000): `check` compiles 4002 cells
and parses the notebook twice; `python notebook.py` spends 70% (9.2 of 13.1 s
profiled) registering cells and 22% in `app.run()`; `export script` is
`parse_notebook` 42% + `load_notebook_ir` 48%. Whole-notebook passes per
command at smoke-500, counted with the import hook:

| command | `parse_notebook` | `compile_cell` per cell | other |
| --- | --- | --- | --- |
| `check` | 2 | 2 | – |
| `export script` | 1 | 1 | – |
| `export html` | 1 | 3 (load, codegen for the embedded source, kernel) | 501 fingerprints |
| `python notebook.py` | 0 (Python imports the file) | 1, plus 1 extra `ast.parse` and 5–6 tokenize passes per cell | – |

### M8. Import / startup (`python -X importtime`, min of 3 runs per module, contended wall)

| | modules imported | sum of self times |
| --- | --- | --- |
| `import marimo` | 889 | 692 ms |
| `marimo edit nb.py` until the first HTTP 200 | 1345 | 1196 ms |

Largest pieces of `import marimo` (self time, modules): `marimo._runtime`
96 ms/113, `marimo._plugins` 74 ms/89, `marimo._utils` 59 ms/48 (35.8 ms is one
regex, F14), `narwhals` 41 ms/58, `marimo._ast` 31 ms/24, `marimo._save`
21 ms/28, `marimo._lint` 19 ms/32, `yaml` 18 ms/18, `asyncio` 18 ms/29,
`markdown` 14 ms/13. Added by `marimo edit`: `marimo._server` 155 ms/122
(64.5 ms is `endpoints/assets.py`, F14), `marimo._cli` +40 ms, `websockets`
27 ms, `starlette` 21 ms, `uvicorn` 18 ms, `marimo._export` 20 ms/14,
`marimo._lint` 29 ms.

### M9. Not measured

- How often the editor saves and how often `_mirror` fires while typing: the
  per-call costs are measured, the frequency belongs to the frontend/wire
  reports.
- A calm-machine rerun of the save and CLI tables; treat their absolute values
  as ≈1.5–2× high and use the ratios.
- `export html` time split inside the kernel thread (cProfile does not follow
  it; py-spy needs root on macOS).

## Findings (highest impact first)

### F1. Every save recompiles and re-serializes all cells; nothing is reused between saves

- **Category:** caching
- **Where:** `marimo/_ast/codegen.py:642` (`generate_filecontents` →
  `TopLevelExtraction.from_codes`), `marimo/_ast/toplevel.py:125`
  (`TopLevelStatus.update` calls `compile_cell` for every cell),
  `marimo/_ast/codegen.py:524` (`safe_serialize_cell` re-parses every generated
  cell), `marimo/_ast/codegen.py:213` (`format_markdown` tokenizes every
  markdown cell). Reached from `AppFileManager.save_from_cells`
  (`marimo/_session/notebook/file_manager.py:456`), which is called by
  `SessionBridge._write` (`marimo/_server/host/bridge.py:374`) for editor saves
  and by `NotificationListenerExtension._maybe_autosave`
  (`marimo/_session/extensions/extensions.py:362`) for code-mode autosaves.
- **Evidence:** MEASURED (M4, M5). A save with one edited cell costs the same
  as a save where nothing changed, because codegen runs before
  `NotebookWriter.content_matches_last_save`
  (`marimo/_session/notebook/writer.py:137-142`).
  At smoke-500 one save is ≈8 whole-file parses (≈0.3 s calm, 0.3–0.6 s
  measured under contention); 81–82% of codegen is 500 `compile_cell` calls
  and 10% is 501 defensive `ast_parse` calls. Scaling is linear (slope ≈1.1),
  so this is "all N cells per save", not O(n²).
- **Why it is slow:** the IR handed to codegen is plain strings, so
  `TopLevelStatus` compiles each cell from scratch (two AST parses, the
  defs/refs visitor, two bytecode compiles) only to read `defs`, `refs`, `mod`
  and `markdown`; then each serialized cell is parsed once more to prove it is
  valid Python. The session already holds compiled cells for unchanged code,
  but nothing links them to the save.
- **Proposed fix:** memoize the static analysis by source text. Smallest
  version: an LRU keyed on `code` in `toplevel.py` returning a copy with a
  fresh `config`/`cell_id` (`prototypes.py: apply_codegen_compile_cache`), plus
  a set of hashes of serialized cell text already proven to parse
  (`apply_safe_serialize_cache`). Better version: split `compile_cell` into
  `analyze_cell(code)` (AST, defs, refs, variable data, markdown; no bytecode)
  and a lazily built code object, and let codegen, lint and the host analyzer
  share one analysis cache (also removes the second parse and both bytecode
  compiles from those paths, F7). `format_markdown` can use the same key.
- **Expected impact:** save with one edited cell 308 → 21 ms (15×) at 500
  cells, 1.9 s → 78 ms (24×) at 2000, 387 → 22 ms on `outputs-500`
  (contended CPU, A/B). What remains is per-cell string assembly.
- **Effort / risk:** S for the LRU (the prototype passes `tests/_ast` codegen,
  parse and toplevel tests); M for the `analyze_cell` split. Risk: a cached
  `CellImpl` has mutable members (`config`, runtime state), so the cache must
  hand out copies; local names are mangled with the cell id, so key or re-mangle
  accordingly (codegen output was byte-identical in the prototype on all
  fixtures).

### F2. Opening a notebook parses the file 4× and compiles every cell 5×, four of them in the server, which never runs a cell

- **Category:** caching, lazy-init
- **Where:** `marimo/_cli/utils.py:130` (`check_app_correctness` →
  `get_notebook_status`); `marimo/_server/api/endpoints/assets.py:397` and
  `marimo/_server/host/api.py:246` (`session_manager.app_manager(...)` builds a
  whole `AppFileManager` to read `app.config` / `app.path`) →
  `marimo/_server/session_manager.py:199` → `marimo/_server/workspace/_base.py:88`;
  session creation (same `workspace.load`); `marimo/_server/host/bridge.py:273`
  (`_file_manager`, from `_read` at :255, used by `_initialize_notebook` at
  :202); `marimo/_server/host/analysis.py:80` (`CellAnalyzer.__call__`);
  eager compile itself at `marimo/_ast/cell_manager.py:264` (`register_ir_cell`
  → `ir_cell_factory`).
- **Evidence:** MEASURED call counts (M3): 4 `parse_notebook`, 3 `load_app`,
  2004 server-side + 501 kernel-side `compile_cell`, 2004 `code_fingerprint`
  for a 501-cell notebook. In stage units from M1 that is 3 × `load_app` +
  1 `parse_notebook` + 1 compile pass ≈ 1.5 s of calm single-thread CPU at 500
  cells (INFERRED from M1 medians; 6.6 s wall was observed under contention),
  against 0.18 s for the one compile the kernel needs. Nothing under
  `marimo/_server`, `marimo/_session` or `marimo/_core` reads compiled cells or
  the graph of an `AppFileManager` (grep for `valid_cells`, `.cells()`,
  `.graph`, `execution_order`, `_compiled_cells`, `.cell._cell`); the only
  consumers are the AI dependency-graph tool
  (`marimo/_ai/_tools/tools/dependency_graph.py:110`) and export
  (`marimo/_export/file.py:156`), and `CellManager.unparsable` is only read by
  lint. The host websocket route (`api.py:246`) was not exercised by
  `ws_traffic.py`, so its load is INFERRED from the code and not in the count.
- **Why it is slow:** `AppFileManager(path)` is the only way to get at a
  notebook's cells or config, and it always parses *and* compiles; four
  independent call sites each build their own; the host layer then compiles
  and fingerprints again with separate caches.
- **Proposed fix:** (1) compile lazily: `register_ir_cell` stores the IR and
  `CellManager` compiles on first `cells()`/`valid_cells()`/graph access, so
  server-side loads cost one `parse_notebook`. (2) Do not load at all where
  only metadata is needed: the index page and the host websocket should use the
  live session's manager, or a parse-only helper that returns
  `AppInstantiation.options`; `SessionBridge._read` needs code/name/config,
  which the IR already has (`documents.from_ir`). (3) Reuse the pre-flight
  parse (cache `parse_notebook` on `(path, mtime, size)` or pass the
  `LoadResult` on). (4) One analysis cache keyed on code (F1) shared by
  `CellAnalyzer` and codegen.
- **Expected impact:** server-side work at open drops from ≈8 file-parse
  equivalents + 4 compile passes to 1 parse + 1 analysis pass; at 500 cells
  ≈1.5 s → ≈0.4 s calm CPU, before the F3 parse speed-up.
- **Effort / risk:** M. Lazy compile changes when a `SyntaxError` is first
  seen (today at load); run mode, export and `marimo run` must still fail
  early, so keep an explicit `ensure_compiled()` for them.

### F3. `parse_notebook` spends ≈70% of its time re-tokenizing each cell four times in `fixed_dedent`

- **Category:** algorithms
- **Where:** `marimo/_ast/dedent.py:159` (`fixed_dedent`, tokenizes at :170)
  and `:124` (`smart_dedent`, tokenizes the same text again at :134); called
  twice per cell from `marimo/_ast/parse.py:249` (`extract_from_code`, on the
  whole decorated function, which is already flush-left) and `:375`
  (`to_cell_def`, on the cell body).
- **Evidence:** MEASURED. 1002 `tokenize.generate_tokens` passes for the 250
  cells of smoke-250; `parse_notebook` is 4.9× a plain `ast.parse` of the file
  (M1); replacing the dedent with `textwrap.dedent` makes it 3.4× faster, so
  ≥70% of `parse_notebook` is this (M5). cProfile: 0.84 of 1.02 s
  (`prof/parse_notebook_smoke500.prof`).
- **Why it is slow:** Python's `tokenize` yields one `TokenInfo` per token from
  Python code, and it runs four times over every cell: `fixed_dedent` and then
  `smart_dedent` on its output, for the function and again for the body.
- **Proposed fix:** `../patches/backend-load-save-dedent-fast-paths.patch`:
  return immediately when the first line with content has no indentation (the
  function-level call), and reuse the protected-line rows instead of
  re-tokenizing when only blank lines were padded (the body call). Further
  step for text sliced from a parsed file (`parse.py` only): skip tokenizing
  when no token can span lines (no triple quote, backslash-newline or f/t-string
  prefix), `prototypes.py: fast_fixed_dedent_valid_source`.
- **Expected impact:** tokenize passes per cell 4 → 1 (→ ≈0.5 with the further
  step); `parse_notebook` 2.2–2.3× faster (2.7–2.9×), i.e. 182 → ≈80 ms calm at
  500 cells, on every load (×4 per open, F2), reload, `check`, export, and in
  script mode (`cell_factory` dedents three times per cell).
- **Effort / risk:** S. The patched function is output-identical to the
  current one on 294k fuzzed inputs (`fuzz_patched_dedent.py`: fixture cells
  plus random indentation, tab, `\r`, truncation and unterminated-string
  mutations) and passes `tests/_ast/test_dedent.py`. The valid-source variant
  is only equivalent for tokenizable input, so keep it out of the general
  function.

### F4. Host document fingerprints (`ast.parse` + `ast.dump` + sha256 per cell) are recomputed for every cell on every save, twice, and on every document transaction

- **Category:** caching
- **Where:** `marimo/_core/document.py:99` (`DocumentCell.__post_init__` →
  `code_fingerprint`, `marimo/_core/code.py:18`); built for all cells by
  `marimo/_server/host/document.py:62` (`sources`) from
  `marimo/_server/host/bridge.py:375` (`_write`), `:544` (`persisted`, the
  `on_persisted` callback, computed even though `_saved` then ignores it while
  `_saving`), `:615` (`_mirror`, on each
  `NotebookDocumentTransactionNotification`,
  `marimo/_server/host/backend.py:531`), `:176/:216/:490/:502`.
- **Evidence:** MEASURED cost: one `Document(sources(cells))` is 84 ms at
  smoke-500, 132 ms at outputs-500, 419–587 ms at 2000 cells (contended CPU),
  i.e. ≈1.4× a full `ast.parse` of the file; 4 passes at open (M3), 2 per save.
  INFERRED: how often `_mirror` fires during editing (not driven here).
- **Why it is slow:** `DocumentCell` is rebuilt from scratch for every cell of
  every snapshot, and its constructor parses and dumps the cell's AST; code
  cells that end in an expression are also tokenized (`ends_with_semicolon`).
- **Proposed fix:** memoize `code_fingerprint` on the source string — already
  written up by the wire investigator as
  `../patches/wire-code-fingerprint-cache.patch`; I measured the same
  change. Also drop the redundant `persisted` etag when the save was requested
  through the bridge, and let `_mirror` reuse unchanged `DocumentCell`s by
  `(id, code, name, config)`.
- **Expected impact:** 84 → 3.3 ms per pass at 500 cells (26×), 419 → 16 ms at
  2000; with F1 a full `bridge.save` goes from ≈0.5 s to ≈30 ms contended CPU.
- **Effort / risk:** S. An LRU on a pure function; bound it (the strings are
  already alive in the document).

### F5. Building the dependency graph is O(n²), and O(n³) when definitions come after their uses

- **Category:** algorithms, datastructures
- **Where:**
  (a) `marimo/_runtime/dataflow/graph.py:115-119` (`register_cell` calls
  `is_any_ancestor_stale` and `is_any_ancestor_disabled`, each a full
  `ancestors()` closure, per registered cell);
  (b) `marimo/_runtime/dataflow/edges.py:89` (`get_referring_cells` scans every
  cell) called per def at `:249` and per ref at `:287-292`, where the result is
  then filtered again for deleters;
  (c) `marimo/_runtime/dataflow/topology.py:136` (`get_path`, a BFS that
  copies the path for every visited node) called per edge by
  `detect_cycle_for_edge` (`marimo/_runtime/dataflow/cycles.py:50`);
  (d) `marimo/_runtime/dataflow/__init__.py:116-117` (`induced_subgraph` tests
  membership in `cell_ids`, which `marimo/_ast/app.py:639` passes as a list).
  Paid by `App._maybe_initialize` (`app.py:596`: export, script mode, lint,
  `InternalApp.graph`), by `CellAnalyzer.__call__`
  (`marimo/_server/host/analysis.py:75-88`, which builds a fresh
  `DirectedGraph` and re-registers every cell on each call), and by the kernel.
- **Evidence:** MEASURED (M1 graph table, M5). chain: slope 2.0–2.1, 1.28 s
  calm / 2.4–2.9 s contended at 2000 cells, 92% of it in the two ancestor
  walks (575 + 544 of 1220 ms, run 1); smoke/outputs (star graph): slope
  ≈1.8, 0.27–0.39 s at 2000, in (b); reversed chain: 2.8 s at 2000 in (c)
  alone, growing ≈7× per doubling. (d) is real but small (165 ms of
  `topological_sort` at chain-2000, run 1) and hidden behind (a).
- **Why it is slow:** each registration re-derives global facts — "is any
  ancestor stale/disabled", "who references this name", "does this edge close a
  cycle" — by walking the whole graph instead of keeping an index or doing one
  pass after bulk registration.
- **Proposed fix:** (a)+(b) are in the runtime investigator's
  `../patches/backend-runtime-proposed.patch` (F6 name → cells
  index, F7 early-exit ancestor checks). For bulk loads I would go further and
  add `DirectedGraph.register_cells(...)` that adds all nodes/edges and then
  resolves stale/disabled in one topological pass and cycles with one SCC pass
  (`prototypes.py: apply_graph_bulk_register`). (c): predecessor-map BFS
  (`apply_get_path_predecessors`, same paths and cycles reported). (d):
  `../patches/backend-load-save-induced-subgraph-set-membership.patch`.
  `CellAnalyzer` should keep its graph and re-register only changed cells.
- **Expected impact:** graph build 2674 → 25 ms at chain-2000 (106×),
  163 → 6.4 ms at chain-500, 298 → 20 ms at smoke-2000, 21 → 4.9 ms at
  smoke-500; reversed chain-2000 3.2 s → 0.76 s with (c) alone (still
  quadratic until cycles are found in bulk).
- **Effort / risk:** M. The bulk pass marks a cell transitively disabled even
  if its disabled ancestor is registered after it, which per-cell registration
  misses today (arguably a fix, but a behaviour change).

### F6. Codegen rebuilds the set of SQL definitions from every notebook variable for every cell: O(cells × variables)

- **Category:** algorithms
- **Where:** `marimo/_ast/codegen.py:387-395` (`to_functiondef`, `sql_defs`).
- **Evidence:** MEASURED. Save exponent 1.4 on `chain` (one def per cell) vs
  1.1 on `smoke` (no defs, so the branch is skipped); `safe_serialize_cell`
  goes 45 → 508 ms from chain-500 to chain-2000 (11× for 4×). Fix alone:
  451 → 181 ms codegen at chain-2000; the committed test sees it as n^1.11 in
  function calls.
- **Why it is slow:** `variable_data` is `extraction.variables`, the dict of
  every variable in the notebook; iterating it inside the per-cell function is
  quadratic for any notebook whose cells define things — i.e. most real ones.
- **Proposed fix:** `../patches/backend-load-save-codegen-sql-defs-per-cell.patch`
  (look up only `cell.defs`).
- **Expected impact:** chain-2000 save 453 → 44 ms together with F1 (10×),
  2.5× on its own; no change for the smoke shape.
- **Effort / risk:** S, identical output (asserted on all fixtures, codegen
  tests pass).

### F7. `compile_cell` does work its callers never use: a second AST parse, two bytecode compiles, a Python-level tokenize pass

- **Category:** lazy-init, algorithms
- **Where:** `marimo/_ast/compiler.py:284` (`original_module =
  module_compile(code)`, a re-parse used as a deep copy), `:331-336` (bytecode
  for body and last expression, compiled even for codegen, lint, the host
  analyzer and server-side loads), `:287` → `marimo/_core/code.py:47`
  (`ends_with_semicolon` tokenizes the whole cell whenever the last statement
  is an expression).
- **Evidence:** MEASURED (M2): of 508 ms for 501 cells, 175 ms is the two
  parses (so ≈88 ms, 17%, is the duplicate), 81 ms (16%) bytecode, 169 ms (33%)
  the defs/refs visitor. `ends_with_semicolon` is 78 ms (12%) on outputs-500.
- **Why it is slow:** the visitor mangles names in place, so an unmangled tree
  is obtained by parsing again; bytecode is produced eagerly; the semicolon
  check uses the pure-Python tokenizer on the full source to look at one
  trailing token.
- **Proposed fix:** make `CellImpl.mod` and the code objects lazy (or split
  out `analyze_cell`, F1); `../patches/backend-load-save-ends-with-semicolon-fast-path.patch`
  returns `False` when the source contains no `;` at all.
- **Expected impact:** INFERRED ≈30% off every non-executing compile (codegen,
  lint, analyzer, server loads); MEASURED 1.2× on `load_notebook_ir` for
  output-heavy notebooks from the semicolon fast path (390 → 335 ms at
  outputs-500), also applies to `code_fingerprint`.
- **Effort / risk:** S for the fast path (exact); M for lazy fields
  (`CellImpl` is a frozen dataclass constructed in several places).

### F8. `marimo check` compiles every cell twice and parses the notebook twice

- **Category:** caching
- **Where:** `marimo/_lint/rules/runtime/reusable_definition_order.py:285`
  (`_extract_notebook` calls `compile_cell(..., filename=filename)` for every
  cell although `LintContext.get_graph`, `marimo/_lint/context.py:206`, has
  already compiled them); the `filename=` argument routes through
  `marimo/_ast/compiler.py:424` (`solve_source_position`) →
  `:393` (`_build_source_position_map`), which re-reads and re-parses the whole
  notebook, then scans all cells linearly per cell (`:432`).
- **Evidence:** MEASURED (M7, `prof/check-smoke-2000.prof`): 4002
  `compile_cell` for 2001 cells, 2 `parse_notebook`; `_extract_notebook` is
  10.2 of 22.4 s profiled. `check` costs 3.3 ms/cell net of startup vs 1.5 for
  `export script`.
- **Why it is slow:** the rule wants `TopLevelExtraction` in notebook order
  with source positions and builds both from scratch.
- **Proposed fix:** build the extraction from the graph's `CellImpl`s
  (`TopLevelExtraction.from_cells`), and take positions from the IR
  (`cell.lineno`, `cell.col_offset` are already on each `CellDef`) instead of
  `filename=`.
- **Expected impact:** `check` on smoke-500 2.47 → ≈1.7 s CPU (INFERRED: one
  compile pass and one parse fewer, i.e. about the 0.73 s that `export script`
  spends on one of each).
- **Effort / risk:** S. Diagnostics must keep the same line numbers.

### F9. Script mode re-derives each cell from source before running anything

- **Category:** algorithms
- **Where:** `marimo/_ast/compiler.py:607-644` (`cell_factory`:
  `inspect.getsourcelines`, `smart_dedent`, `parse.Extractor`, `ast_parse`,
  `to_cell` with two `fixed_dedent`s, then `compile_cell`), called per
  `@app.cell` from `marimo/_ast/cell_manager.py:122`.
- **Evidence:** MEASURED (`prof/run-smoke-2000.prof`): cell registration is
  9.2 of 13.1 s profiled, `app.run()` 2.9 s. `python smoke-500.py` is 1.88 s
  CPU, of which 0.57 s is `import marimo` and ≈1.3 s registration + run.
- **Why it is slow:** after Python has compiled the module, each decorated
  function's source is fetched, dedented (three dedents = 5–6 tokenize passes),
  parsed once to find the body and twice more inside `compile_cell`.
- **Proposed fix:** F3 removes most of the tokenizing; reuse the `ast_parse`
  result for the body instead of re-parsing in `compile_cell` (pass the module
  in); F7 for the rest.
- **Expected impact:** INFERRED ≈20–25% of registration from F3 alone (the
  dedents are ≈3.0 of the 9.2 s in the profile), more with the single parse.
- **Effort / risk:** S–M.

### F10. A file-watch reload is a full load, plus an O(n²) similarity match when many cells changed

- **Category:** caching, algorithms
- **Where:** `marimo/_session/notebook/file_manager.py:171` (`reload` →
  `_load_app`), `:172` → `marimo/_ast/cell_manager.py:545` →
  `marimo/_utils/cell_matching.py:323` (`similarity_score` for every
  added × deleted pair, a Python character loop at `:12`).
- **Evidence:** MEASURED (M6): one changed cell → reload ≈ `load_app` (763 ms
  contended at smoke-500), matching 0.8 ms. All cells changed (formatter or
  agent rewrite): matching 896 ms at 500 cells, 2.3 s at chain-1000, exponent 2.
- **Why it is slow:** unchanged cells are recompiled; the matcher only
  short-circuits exact code matches and scores every remaining pair.
- **Proposed fix:** reuse analysis by code (F1/F2); in the matcher, pair
  leftovers that kept their position before falling back to all-pairs, and/or
  bucket by first line.
- **Expected impact:** single-cell reload ≈ parse only (≈80 ms calm at 500
  cells with F3); bulk rewrites linear.
- **Effort / risk:** S–M; matching heuristics affect which cell keeps its id
  (and so its output).

### F11. The garbage collector adds 25–35% to whole-file parsing

- **Category:** algorithms
- **Where:** `marimo/_ast/parse.py:1083` (`parse_notebook`: one large AST is
  alive while per-cell strings and tokens are allocated).
- **Evidence:** MEASURED, interleaved A/B with `gc.disable()`: `ast.parse` of
  the file 70 → 46 ms (1.52×) at smoke-500 and 290 → 207 ms at 2000;
  `parse_notebook` 354 → 287 ms (1.24×) and 1675 → 1245 ms (1.35×);
  `load_notebook_ir` 1.02–1.11×; codegen 1.00–1.12×. This is also why M1 slopes
  sit at 1.15–1.2 rather than 1.0.
- **Why it is slow:** every young-generation collection walks into the large,
  fully reachable tree.
- **Proposed fix:** pause collection for the duration of `parse_notebook`
  (restore the previous state in `finally`), or `gc.freeze()` the tree.
- **Expected impact:** −20–26% on `parse_notebook`, stacking with F3.
- **Effort / risk:** S; process-global switch, so keep the window to the parse.

### F12. `NotebookDocument` looks cells up by scanning, and loading applies one transaction per cell

- **Category:** datastructures, batching
- **Where:** `marimo/_messaging/notebook/document.py:113,120,132,279,293`
  (`get_cell`, `get`, `__contains__`, `_find_index`, `_find_cell` are linear);
  `:145-156` and `:346` (`apply` copies the cell list and `_validate` rebuilds
  the id set per transaction); `marimo/_ast/cell_manager.py:236`
  (`register_cell` applies one `CreateCell` transaction per cell). Linear
  lookups inside per-cell loops: `marimo/_convert/ipynb/from_ir.py:113`,
  `marimo/_runtime/app/script_runner.py:92`, `marimo/_session/state/serialize.py:417`,
  `marimo/_ast/app.py:310`.
- **Evidence:** MEASURED (M5): 2001 one-cell transactions 80 → 1.6 ms as one
  batch; `get_cell` for every cell 47 → 0.5 ms with an id index at 2000 cells;
  `cell_data_at` in ipynb export 9 ms at 500 vs 58 ms at 2000 (profile).
- **Why it is slow:** the document is a list with no id index.
- **Proposed fix:** keep `dict[CellId_t, int]` (or cells in an ordered dict)
  maintained by `_apply_change`; register loaded cells in one transaction.
- **Expected impact:** small at 500 cells (≈5 ms per load, 2 ms per
  full-notebook lookup loop), 50–130 ms at 2000; removes a quadratic trap for
  every future per-cell loop.
- **Effort / risk:** S–M; the document is the session's source of truth.

### F13. Each save that changes the file runs four full-text regex passes to compare against the last write

- **Category:** algorithms
- **Where:** `marimo/_utils/generated_with.py:11-21` (`_strip_version` on both
  texts), from `marimo/_session/notebook/writer.py:165`.
- **Evidence:** MEASURED: 11 ms for the 406 KB smoke-500 text (12 ms in M4,
  47 ms at 2000); a variant that stops at the first `__generated_with` line and
  only looks for `marimo-version:` when present: 0.06 ms.
- **Why it is slow:** two `re.sub` over each text, although the version line
  is in the first few lines.
- **Proposed fix:** `../patches/backend-load-save-generated-with-first-match.patch`
  (first match only; look for `marimo-version:` only if the text contains it).
- **Expected impact:** −11 ms per save at 500 cells.
- **Effort / risk:** S.

### F14. Startup: `import marimo` loads 889 modules; several are import-time work or imports that only some features need

- **Category:** lazy-init
- **Where / evidence (MEASURED, M8; self time is min of 3 contended runs):**
  - `marimo/_utils/url.py:14-95`: a ≈3 KB regex compiled at import, **35 ms**;
    reached from `marimo/_output/md.py:30` on every `import marimo`. Patch:
    `../patches/backend-load-save-url-lazy-regex.patch`.
  - `marimo/_server/api/endpoints/assets.py:62-64,98`: reads the user config
    and lists the static directory at import, **64 ms** of `marimo edit`.
  - `marimo/_runtime/runtime.py:48` imports `marimo._lint` (32 modules, 19 ms).
  - `marimo/_sql/utils.py:12` imports `marimo._runtime._wasm._duckdb`
    (19 modules, ≈30 ms cumulative) on CPython.
  - `marimo/_data/data_source_discovery/plugins/pyiceberg.py:10` imports
    `yaml` (18 modules, 18 ms), pulled in by `marimo/_messaging/notification.py:26`.
  - `marimo/_plugins/core/media.py:11` imports `narwhals` (58 modules, 41 ms),
    pulled in by `marimo/_messaging/msgspec_encoder.py:21`.
  - `marimo/_output/md.py` pulls `markdown`, `urllib.request` → `http.client`
    → `ssl`, `email`.
- **Why it is slow:** `marimo/__init__.py:104-165` imports the whole public
  API eagerly and those modules import feature-specific dependencies at module
  scope. The cost is paid by the server, by every kernel process, and by every
  CLI and script-mode run (0.57 s CPU contended; `marimo --version` 0.81 s).
- **Proposed fix:** the url patch and reading the server config on first use
  in `assets.py` first; then move the listed imports into the functions that
  need them.
- **Expected impact:** ≈35 ms off every `import marimo` and ≈65 ms more off
  `marimo edit` from the first two; INFERRED another 100–150 ms of the 692 ms
  from the lazy imports.
- **Effort / risk:** S each; import cycles are the usual hazard.

### F15. Export paths: one avoidable compile pass in `export html`, per-cell ancestor walks in `export script`

- **Category:** caching, algorithms
- **Where:** `export html` regenerates the notebook source through full
  codegen (`generate_filecontents` ← `to_py`), i.e. F1 once more;
  `marimo/_convert/script.py:54` (`cell._is_coroutine` per cell →
  `marimo/_runtime/runner/by_refs.py:98` → `_get_ancestors`, an ancestor walk
  per cell);
  `marimo/_convert/ipynb/from_ir.py:113` (F12).
- **Evidence:** MEASURED counts (M7): 3 compiles per cell in `export html`;
  `_is_coroutine` 52 ms at smoke-500 vs 472 ms at smoke-2000 in the profile
  (the first call also triggers the F5 graph build). On chain-2000, 97% of
  `export script` (29.1 of 29.9 s profiled, `prof/script-chain-2000.prof`) is
  the `_is_coroutine` loop: 11.2 s graph build (F5) plus 17.8 s of per-cell
  ancestor walks.
- **Proposed fix:** F1's cache covers html; for script export, check
  `CellImpl.is_coroutine()` on each cell directly (a notebook is async iff some
  cell is) instead of walking ancestors per cell.
- **Expected impact:** small for the smoke shape; removes an O(n × depth) walk
  on dependency chains.
- **Effort / risk:** S.

## Ruled out

- **Session cache write** (`SessionCacheWriter`, `__marimo__/session/*.json`,
  every 2 s while anything changed): `serialize_session_view` 2.6 ms +
  re-reading the notebook for `script_metadata_hash` 2.8 ms + `json.dumps(indent=2)`
  0.8 ms for a real outputs-500 session (299 KB); 8.6 + 11 + 2.9 ms at 2000
  (`bench_session_cache.py`). It is also disabled in edit mode when
  `auto_instantiate` is on (`marimo/_session/session.py:193`).
- **Header re-read on save** (`get_header_comments`): 0.3 ms at 500 cells.
- **`notebook_file_lock`**: 0.06 ms per save. (It leaves one zero-byte file
  per saved notebook path in `~/.local/state/marimo/notebook-locks` and never
  removes it: 370 files there now, 127 from today's benchmark and test runs
  across investigators. Not a speed issue.) **`storage.write`**: 1.4 ms.
- **`copy.deepcopy(session.document.cells)`** before each save: 1.9 ms at 500,
  8.6 ms at 2000. **`cells_to_ir`**: 0.5 ms.
- **Cell id generation**: 0.8 ms per 500 cells.
- **`warnings.catch_warnings` around every `compile`** (`compiler.py:47`):
  ≈5 µs per call (501 parses: 29.2 ms raw vs 31.8 ms wrapped).
- **`TopLevelExtraction.__init__`** (set copies per status): 2.5 ms at 500,
  10 ms at 2000.
- **`get_closure_refs`**, **`_extract_markdown`**, **`contains_only_tests`**:
  ≤1% of `compile_cell` each.
- **Cycle detection for notebooks in definition order**: 0.5 ms at chain-500
  (it is only the reversed order that is slow, F5c).
- **Layout files**: written only by an explicit layout save
  (`AppFileManager.save_layout`), not per save.
- **`_approximate_assignment` in cell matching**: 54 ms of 896 ms at 500
  changed cells; the pairwise scoring dominates (F10).

## Benchmarks added

- `tests/_ast/test_large_notebook_perf.py` — generates 40- and 160-cell
  `smoke` and `chain` notebooks into `tmp_path` with
  `scripts/benchmarks/generate_large_notebook.py`, loads them with
  `AppFileManager`, saves one edited cell with `save_from_cells`, asserts the
  cell count, codes and names round-trip through a reload, and asserts that
  load and save work (function calls under `cProfile`, like
  `tests/_runtime/test_large_notebook.py`) grows with exponent < 1.5.
  Today: smoke load n^1.00 / save n^0.99, chain load n^0.98 / save n^1.11.
  Call counts do not see loops that make no calls, so F6 shows only mildly and
  F12 not at all; graph build is not asserted because it is quadratic today
  (F5).
  Run: `.venv/bin/python -m pytest tests/_ast/test_large_notebook_perf.py -q -s`.
  **`.venv` has no pytest** (the `test` dependency group is not installed), so
  I ran it from a scratch venv layered over `.venv`:
  `.context/perf/backend-load-save/.venv-test/bin/python -m pytest tests/_ast/test_large_notebook_perf.py -q -s`
  → 2 passed. `ruff check` and `ruff format --check` pass.
- Scratch (not for commit), all in `.context/perf/backend-load-save/`:
  `bench_load.py`, `bench_compile.py`, `bench_save.py`, `bench_prototypes.py`
  - `prototypes.py`, `bench_reload.py`, `bench_cli.py` + `cli_summary.py`,
  `bench_session_cache.py`, `run_session.sh` + `hook/sitecustomize.py` +
  `summarize_counts.py` (call counts in a live `marimo edit`),
  `fuzz_dedent.py` / `fuzz_patched_dedent.py`, `pytest_plugin.py` (repo tests
  with the prototypes applied), `patched_plugin.py` (repo tests against the
  patched file copies in `patchwork/b`).
- Patches (all pass `git apply --check` on the current tree):
  `../patches/backend-load-save-{dedent-fast-paths,codegen-sql-defs-per-cell,ends-with-semicolon-fast-path,induced-subgraph-set-membership,generated-with-first-match,url-lazy-regex}.patch`.
