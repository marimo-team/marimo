# Kernel runtime — large-notebook performance

Scope: what the kernel costs to instantiate and operate a 500-cell notebook once
the code is loaded (`marimo/_runtime/**`, `marimo/_messaging/**`, the runner
hooks). Production source was not edited. Fixes were proven by monkeypatch
(`.context/perf/backend-runtime/patches.py`) and, for most findings, as a real
diff applied to a private copy of `marimo/`
(`../patches/backend-runtime-proposed.patch`).

**Headline.** The user code in the smoke notebook is ~14 µs per code cell. The
kernel spends ~1.4–2.3 ms CPU per code cell around it (~95–180x), almost all of it in
six places that have nothing to do with the cell: per-cell fd redirection
(2 pipes + 2 threads per cell), a duckdb hook that re-parses every cell, an
entry-point scan on every run, and three O(n) rescans done once per cell. With
the default `runtime.auto_instantiate = false`, running **one** cell of a
500-cell notebook costs 310–430 ms CPU because every still-pending cell is
recompiled per run request. All of it is fixable without protocol changes:
run phase at smoke-500 **351 → 58 ms CPU** (-83%; 2,043 → 165 ms at 2000
cells), single-cell run under lazy startup **~350 → ~5 ms**, single-cell run
on a 500-deep chain **32 → 2.7 ms**, chain-2000 run-all **13.0 → 1.8 s**.

## Measurements

### Method (read this before trusting any absolute number)

- **Harness**: `.context/perf/backend-runtime/harness.py` builds a real `Kernel`
  through `kernel_session()` (the code path `launch_kernel` uses) in edit mode,
  with the production stream classes — `ThreadSafeStream(redirect_console=True)`
  and `ThreadSafeStdout/Stderr(forward_os_streams=True)`, i.e. the per-cell
  `os.dup2` redirection an edit-mode kernel subprocess performs. Only the
  transport is replaced (a pipe object that counts bytes). `DEFAULT_CONFIG`.
  One fresh process per measurement. `PERF_NAMED=1` passes the notebook path as
  `app_metadata.filename`, as `marimo edit file.py` does.
- **The machine was heavily loaded the whole time** (load average 30–360 on 14
  cores; other investigators running browsers and builds). Wall-clock is
  therefore unreliable, and syscall-heavy paths (thread start, pipes, `getcwd`)
  inflate far more than pure Python. I report, in order of trust:
  1. **Python function calls** (`cProfile` `total_calls`) — deterministic,
     identical run to run.
  2. **Process CPU time** (`time.process_time`, all threads), min of 3, with
     baseline and patched runs **interleaved** (`compare.py`).
  3. Wall-clock min of 3, for reference only.
  CPU numbers are still ~1.3–2x higher than on a quiet machine (my first run,
  before the load spiked: smoke-500 instantiate **596 ms wall**, of which
  compile+markdown 207, register 7.5, run 355; smoke-2000 3750 ms).
- **"exec-only" baseline**: `exec()` of the pre-compiled cell bodies in one
  namespace, warm, min of 5 (`harness.baseline_exec`). Reported for the cells
  the runner actually executes ("graph cells") and for all cells.
- **Cross-check in a real server**: `marimo edit smoke-500.py --headless --port
  29811 --profile-dir …`, instantiated over the WebSocket with
  `scripts/benchmarks/ws_traffic.py`; the kernel subprocess's own cProfile dump
  is in `.context/perf/backend-runtime/e2e/prof/`. Server was killed afterwards.
- "Prototypes" = all monkeypatches in `patches.py` (`--patch all`). "Diff" = the
  proposed production diff (`PERF_OVERLAY=1`). Both leave the per-cell
  notification stream identical (`check_parity.py`, smoke/outputs/chain-100:
  0 of 103 cells differ, modulo `set` ordering inside `variables`).

Scripts (all in `.context/perf/backend-runtime/`): `bench_runall.py`,
`compare.py`, `matrix.py`, `bench_incremental.py`, `bench_pending.py`,
`bench_dataflow.py`, `ablate.py`, `micro_*.py`, `profile_runall.py`,
`check_parity.py`. Raw results: `cmpf_*.jsonl`, `cmpo_*.jsonl`, `inc_*.jsonl`,
`df_*.jsonl`, `m_*.jsonl`, `msgs_*.json`.

### M1. Instantiate = compile + register + run-all

`kernel.instantiate(CreateNotebookCommand(auto_run=True))`.
`python compare.py smoke 50,100,250,500,1000,2000 3 all` (PERF_NAMED=1).
In `smoke`/`outputs` the markdown cells are rendered inside
`_handle_markdown_cells_on_instantiate` and never enter the graph, so "graph
cells" is the number of cells the runner executes.

**smoke (star; the target notebook)** — CPU ms, min of 3, base → all prototypes:

| cells (in graph) | calls | total | compile + md | `mutate_graph` | run phase | run µs/cell | exec-only (graph cells) | run ÷ exec | msgs / bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 (26) | 0.34M → 0.26M | 100 → 67 | 39 | 0.6 → 0.6 | **59 → 22** | 2,265 → 850 | 0.34 | 171x → 64x | 311 / 0.12 MB |
| 100 (51) | 0.62M → 0.44M | 180 → 104 | 67 | 1.0 → 0.7 | **109 → 26** | 2,139 → 520 | 0.60 | 183x → 44x | 611 / 0.23 MB |
| 250 (126) | 1.59M → 1.07M | 426 → 222 | 189 | 4.3 → 1.8 | **232 → 37** | 1,840 → 297 | 1.49 | 155x → 25x | 1,511 / 0.58 MB |
| 500 (251) | 3.37M → 2.12M | 670 → 405 | 308 | 10.3 → 3.8 | **351 → 58** | 1,398 → 232 | 3.75 | 94x → 16x | 3,011 / 1.17 MB |
| 1000 (501) | 7.73M → 4.30M | 1,876 → 793 | 799 | 38.3 → 12.8 | **1,037 → 94** | 2,070 → 189 | 10.89 | 95x → 9x | 6,011 / 2.37 MB |
| 2000 (1001) | 19.01M → 8.62M | 3,696 → 1,636 | 1,496 | 129.3 → 15.0 | **2,043 → 165** | 2,041 → 165 | 17.94 | 114x → 9x | 12,011 / 4.77 MB |

- Run phase per executed cell: **1.4–2.3 ms CPU** (0.9–1.4 ms wall in my
  least-loaded run) vs **14–18 µs** to `exec` the same cell: **~95–180x**.
- Function calls 500 → 2000 cells grow x5.6 for x4 cells
  (exponent 1.25); from the unpaired 6-size matrix
  (`matrix.py smoke prod 3`, `m_smoke_prod.jsonl`) CPU exponents 500 → 2000:
  total 1.17, `mutate_graph` 1.87, run phase 1.22, bytes 1.01.
- After the prototypes the remaining cost is compile + markdown render
  (84% of what is left at 500 cells) — the load/save
  investigator's area.

**chain and outputs** (`compare.py chain … all`, `compare.py outputs … all`):

| fixture | variant | calls | total CPU ms | `mutate_graph` | run phase | run µs/cell | exec-only ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| chain-100 (101 run) | base → all prototypes | 0.62M → 0.23M | 114 → 36 | 5.2 → 1.3 | 101 → 29 | 1,000 → 283 | 0.01 |
| chain-500 (501 run) | base → all prototypes | 9.52M → 1.99M | 828 → 157 | 110.2 → 8.1 | 682 → 118 | 1,362 → 237 | 0.07 |
| chain-1000 (1001 run) | base → all prototypes | 35.49M → 6.43M | 2,705 → 441 | 436.4 → 14.8 | 2,217 → 371 | 2,215 → 371 | 0.12 |
| chain-2000 (2001 run) | base → all prototypes | 136.93M → 22.81M | 13,000 → 1,759 | 2,782.7 → 35.8 | 10,017 → 1,554 | 5,006 → 777 | 0.24 |
| outputs-500 (251 run) | base → all prototypes | 4.26M → 2.94M | 860 → 436 | 11.7 → 2.8 | 484 → 113 | 1,929 → 451 | 34.94 |
| outputs-2000 (1001 run) | base → all prototypes | 22.87M → 12.03M | 4,456 → 2,747 | 173.6 → 19.0 | 2,578 → 638 | 2,576 → 638 | 154.74 |
| smoke-500 (251 run) | base → proposed diff only | 3.38M → 2.25M | 702 → 511 | 9.6 → 2.9 | 380 → 194 | 1,515 → 775 | 3.40 |
| smoke-2000 (1001 run) | base → proposed diff only | 19.01M → 9.14M | 3,157 → 1,829 | 112.6 → 15.2 | 1,693 → 605 | 1,691 → 604 | 15.15 |
| chain-500 (501 run) | base → proposed diff only | 9.52M → 2.18M | 1,075 → 526 | 135.2 → 58.2 | 904 → 434 | 1,805 → 867 | 0.07 |
| smoke-500 (251 run) | `auto_reload=lazy`: base → all prototypes | 6.94M → 2.30M | 1,791 → 433 | 10.9 → 3.0 | 1,414 → 66 | 5,635 → 264 | 4.07 |

- chain is quadratic: calls 100 → 500 → 2000 = 0.62M → 9.5M → 137M (exponents
  1.70, 1.92); unpaired CPU exponents 500 → 2000: total 1.63, `mutate_graph`
  2.01, run 1.56 (`m_chain_prod.jsonl`). At 2000 cells run-all costs
  **13.0 s CPU** (11.8–14.1 s across three separate runs) for cells that take
  0.24 ms to `exec`.
- Creating the command is not free either: `ExecuteCellCommand.__post_init__`
  fingerprints the source (`ast.parse` + pure-Python `ast.dump` + sha256):
  **183 µs/cell, 86–92 ms for 501 cells** (`marimo/_runtime/commands.py:270`,
  `marimo/_core/code.py:18`). This runs in the server process; the wire
  investigator has `wire-code-fingerprint-cache.patch` for it.

### M2. Where one code cell's ~1.4 ms goes (smoke-500)

Unit costs measured in isolation (`micro_units.py`, `micro_redirect.py`,
`micro_fixed.py`, `micro_misc.py`; CPU, min of 5) and cross-checked against the
pyinstrument tree of a full run (`pyi_smoke_500_prod.txt`) and the per-patch
function-call ablation (`ablate.py smoke 500`, `ablate_smoke_500.jsonl`):

| Per executed cell | CPU µs/cell @500 | @2000 | Calls saved by fixing it (of 3.376M @500) | Finding |
| --- | ---: | ---: | ---: | --- |
| `redirect(stdout)` + `redirect(stderr)`: 2 pipes, 2 threads, EOF waits | 650 (0.9–2.1 ms wall) | 650 | 115k | F2 |
| `_broadcast_duckdb_datasource`: `cell.sqls` re-parse + SQL visitor | 300 | 325 | 600k | F3 |
| `_broadcast_duckdb_datasource`: `DependencyManager.duckdb.has()` | 34–49 (241 for an unnamed notebook) | same | 60k | F3 |
| `ModuleRegistry.modules()` x2 in `_invalidate_cell_state` | 95 | **341** | 381k | F5 |
| `_store_state_reference` set union | 21 | **111** | (C-level) | F9 |
| `_flush_console` round trip to the writer thread | ~50 (0.5 ms under load) | ~50 | — | F12 |
| 8 notifications, built + serialized + written | 18 (2.3 µs each) | 18 | — | ruled out |
| the user's code (`Evaluator.evaluate`) | **14** | 14 | — | — |
| **Per run (not per cell)** `resolve_executor()` entry-point scan | 6500 per run | 6500 | 17.7k per run | F4 |

The same shape shows up in the **real kernel subprocess** profile (smoke-500,
`marimo edit`, kernel cProfile, machine loaded): `instantiate` 3.21 s
cumulative = compile+markdown 1.46 s + `_run_cells` 1.70 s, and inside
`_run_cells`: `streams.py:redirect` **1.525 s** (`_NativePipe.finish` 1.245 s =
2.5 ms per call), `_broadcast_duckdb_datasource` 0.333 s, `invalidate_state`
0.156 s, all notifications 0.253 s (0.145 s of it the pipe `send_bytes`), and
`Evaluator.evaluate` **0.038 s**.

### M3. Notifications emitted during run-all at 500 cells

`python bench_runall.py SHAPE 500 --messages` (hooks the stream's pipe).

| | smoke-500 | outputs-500 | chain-500 |
| --- | ---: | ---: | ---: |
| cells / executed by the runner | 501 / 251 | 501 / 251 | 501 / 501 |
| messages | 3,011 | 3,042 | 5,011 |
| bytes | 1,172,064 | 1,320,625 | 1,198,274 |
| `execution` (planned + running + completed) | 1,503 msgs / 801 KB | 1,503 / 827 KB | 1,503 / 471 KB |
| — of which `planned` (echoes the cell source) | 501 / **523 KB** | — | — |
| `cell-op` status=queued | 251 / 45 KB | 251 / 45 KB | 501 / 89 KB |
| `cell-op` status=running, console=[] | 251 / 53 KB | 251 / 53 KB | 501 / 106 KB |
| `cell-op` output only | 251 / 72 KB | 251 / 184 KB | 501 / 144 KB |
| `cell-op` status=idle | 251 / 53 KB | 251 / 53 KB | 501 / 105 KB |
| `cell-op` idle + output (markdown fast path) | 250 / 131 KB | 250 / 132 KB | — |
| `remove-ui-elements` | 251 / 11 KB | 251 / 11 KB | 501 / 22 KB |
| `variable-values` | 2 | 2 | 1,002 / 231 KB |
| `variables` | 1 / 3.7 KB | 1 / 4.8 KB | 1 / 29.6 KB |
| `cell-op` console | 0 | 31 / 11 KB | 0 |

- **8 messages per executed code cell** (queued, remove-ui-elements, planned,
  running, cell-op running, cell-op output, cell-op idle, completed), 4 per
  markdown cell, +2 `variable-values` per defined variable.
- Bytes are linear in cells (exponent 0.99–1.01 for all three shapes): **no
  notification is O(n) in size and sent O(n) times during a single run-all.**
- One notification is O(n) in size and sent on **every** `mutate_graph`, i.e.
  on every run request: `variables`. A single-cell run sends 3.7 KB at
  smoke-500, 16 KB at smoke-2000, 31 KB at chain-500, **121 KB at chain-2000**
  (see M4). Running n cells one at a time is therefore O(n²) bytes.

### M4. Incremental operations (touching one cell)

`python bench_incremental.py SHAPE N --reps 3 [--patch all]`. After
`instantiate`; CPU ms median of 3; "calls" from one profiled repetition.

| notebook | operation | today: CPU / calls | all prototypes: CPU / calls | msgs | bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| smoke-500 | empty_run | 7.0 ms / 22k | 0.5 ms / 2k | 0 | 0 |
| smoke-500 | rerun_leaf_unchanged | 9.2 ms / 27k | 1.2 ms / 5k | 9 | 6,906 |
| smoke-500 | edit_leaf | 11.1 ms / 37k | 2.6 ms / 12k | 10 | 6,965 |
| smoke-500 | add_cell | 9.4 ms / 25k | 1.1 ms / 4k | 9 | 5,535 |
| smoke-500 | delete_cell | 7.3 ms / 23k | 0.8 ms / 4k | 2 | 3,742 |
| smoke-500 | edit_setup_add_import | 10.5 ms / 40k | 2.3 ms / 14k | 12 | 7,588 |
| smoke-500 | edit_setup_rerun_all | 333.6 ms / 845k | 37.8 ms / 246k | 1,980 | 804,003 |
| smoke-2000 | empty_run | 5.9 ms / 31k | 1.1 ms / 6k | 0 | 0 |
| smoke-2000 | rerun_leaf_unchanged | 8.9 ms / 41k | 2.2 ms / 10k | 9 | 17,856 |
| smoke-2000 | edit_leaf | 10.9 ms / 60k | 3.8 ms / 23k | 10 | 17,917 |
| smoke-2000 | add_cell | 9.5 ms / 39k | 1.7 ms / 10k | 9 | 16,034 |
| smoke-2000 | delete_cell | 6.8 ms / 37k | 1.6 ms / 12k | 2 | 14,242 |
| smoke-2000 | edit_setup_add_import | 12.7 ms / 92k | 4.1 ms / 44k | 12 | 18,086 |
| smoke-2000 | edit_setup_rerun_all | 1659.1 ms / 7,838k | 130.1 ms / 991k | 7,980 | 3,322,922 |
| outputs-500 | empty_run | 7.7 ms / 22k | 0.7 ms / 2k | 0 | 0 |
| outputs-500 | rerun_leaf_unchanged | 10.6 ms / 29k | 2.1 ms / 7k | 9 | 8,151 |
| outputs-500 | edit_leaf | 11.2 ms / 37k | 4.3 ms / 12k | 10 | 8,067 |
| outputs-500 | add_cell | 11.0 ms / 25k | 1.7 ms / 4k | 9 | 6,627 |
| outputs-500 | delete_cell | 8.4 ms / 23k | 1.2 ms / 4k | 2 | 4,819 |
| outputs-500 | edit_setup_add_import | 12.0 ms / 40k | 3.1 ms / 14k | 12 | 8,658 |
| outputs-500 | edit_setup_rerun_all | 483.2 ms / 1,102k | 125.8 ms / 504k | 2,011 | 949,203 |
| outputs-500 | ui_element_update(unbound slider) | 9.3 ms / 28k | 1.8 ms / 8k | 2 | 2,769 |
| chain-500 | empty_run | 25.2 ms / 646k | 0.5 ms / 3k | 0 | 0 |
| chain-500 | rerun_leaf_unchanged | 32.1 ms / 665k | 2.7 ms / 13k | 11 | 31,957 |
| chain-500 | edit_leaf | 33.0 ms / 680k | 3.5 ms / 17k | 12 | 32,014 |
| chain-500 | add_cell | 30.4 ms / 655k | 2.6 ms / 10k | 9 | 31,420 |
| chain-500 | delete_cell | 59.2 ms / 1,308k | 3.4 ms / 18k | 11 | 61,092 |
| chain-500 | edit_first_rerun_all | 631.5 ms / 6,609k | 149.4 ms / 1,726k | 5,002 | 1,194,925 |
| chain-500 | edit_middle_rerun_half | 489.0 ms / 3,526k | 60.2 ms / 562k | 2,512 | 615,011 |
| chain-500 | rename_first_var(breaks chain) | 383.0 ms / 5,889k | 113.9 ms / 1,441k | 3,010 | 784,104 |
| chain-500 | rename_back(repairs chain) | 1118.6 ms / 6,601k | 157.2 ms / 1,724k | 5,002 | 1,194,909 |
| chain-2000 | empty_run | 525.2 ms / 10,028k | 1.0 ms / 11k | 0 | 0 |
| chain-2000 | rerun_leaf_unchanged | 932.4 ms / 10,098k | 9.4 ms / 46k | 11 | 121,465 |
| chain-2000 | edit_leaf | 836.0 ms / 10,157k | 8.9 ms / 61k | 12 | 121,522 |
| chain-2000 | add_cell | 693.7 ms / 10,058k | 5.9 ms / 34k | 9 | 120,922 |
| chain-2000 | delete_cell | 1548.6 ms / 20,114k | 13.0 ms / 65k | 11 | 240,093 |
| chain-2000 | edit_first_rerun_all | 10175.7 ms / 93,876k | 1806.6 ms / 21,900k | 20,002 | 4,788,431 |
| chain-2000 | edit_middle_rerun_half | 5521.6 ms / 50,040k | 572.7 ms / 5,991k | 10,012 | 2,459,409 |
| chain-2000 | rename_first_var(breaks chain) | 8358.7 ms / 90,976k | 1395.4 ms / 20,742k | 12,010 | 3,134,210 |
| chain-2000 | rename_back(repairs chain) | 14178.7 ms / 93,837k | 1576.2 ms / 21,894k | 20,002 | 4,788,323 |
| chain-500 (lazy) | empty_run | 29.8 ms / 646k | 0.5 ms / 3k | 0 | 0 |
| chain-500 (lazy) | rerun_leaf_unchanged | 42.9 ms / 670k | 1.7 ms / 13k | 11 | 31,957 |
| chain-500 (lazy) | edit_leaf | 47.7 ms / 686k | 2.6 ms / 17k | 12 | 32,018 |
| chain-500 (lazy) | add_cell | 43.0 ms / 655k | 2.4 ms / 10k | 9 | 31,422 |
| chain-500 (lazy) | delete_cell | 84.5 ms / 1,308k | 2.8 ms / 18k | 11 | 61,094 |
| chain-500 (lazy) | edit_first_rerun_all | 40.5 ms / 683k | 2.6 ms / 27k | 12 | 31,914 |
| chain-500 (lazy) | edit_middle_rerun_half | 40.5 ms / 685k | 2.5 ms / 28k | 12 | 32,006 |
| chain-500 (lazy) | rename_first_var(breaks chain) | 43.2 ms / 672k | 1.9 ms / 20k | 12 | 31,908 |
| chain-500 (lazy) | rename_back(repairs chain) | 40.6 ms / 677k | 2.6 ms / 26k | 12 | 31,912 |
| chain-500 (lazy) | run_stale_cells | 30.8 ms / 646k | 0.6 ms / 4k | 0 | 0 |
| chain-500 (lazy) | run_stale_cells(after editing first) | 1165.2 ms / 8,578k | 171.2 ms / 2,224k | 4,990 | 1,163,010 |

- **Star (smoke/outputs)**: the cost of one cell is *not* proportional to
  notebook size in CPU (7 → 6–9 ms for 500 → 2000) — it is a fixed ~7 ms, of
  which 6.5 ms is `resolve_executor()` (F4). The O(n) part is the bytes (the
  `variables` payload) and ~10k calls of whole-graph scans.
- **Chain**: one cell costs O(n·depth). An **empty run** (`_run_cells(set())`,
  what a slider drag with no dependents triggers) is 646k calls / 25 ms at 500
  cells and **10.0M calls / 525 ms at 2000**. Everything is dominated by
  `is_disabled` walks and the `variables` rebuild (F7).
- Lazy mode (`on_cell_change = "lazy"`): staleness propagation itself is cheap
  (`graph.set_stale` over a 2000-chain: 1.0 ms; an upstream edit marks 499
  cells stale and emits 12 messages); edits cost the same per-run overhead as
  above. Running the stale cells afterwards is *more* expensive than the same
  cells under autorun (chain-500: 8.6M calls vs 6.6M) because of a per-cell
  `is_any_ancestor_stale` walk (F7).

### M5. Lazy startup: `runtime.auto_instantiate = false` (the default)

`python bench_pending.py SHAPE N [patch]`: `instantiate(auto_run=False)`, then
run single cells one request at a time. CPU ms per single-cell run:

| | 1st | 2nd | 3rd | 4th | 5th, under cProfile (calls) |
| --- | ---: | ---: | ---: | ---: | ---: |
| smoke-500, today | 377 | 427 | 310 | 341 | 840 (1,440,815) |
| smoke-500, proposed diff | 32 | 7.6 | 4.2 | 4.9 | 12 (16,781) |
| smoke-2000, today | 2550 | 2039 | 2462 | 2226 | 3557 (6,802,401) |
| smoke-2000, proposed diff | 58 | 16 | 9.1 | 8.4 | 28 (56,555) |
| chain-500, today (1st run pulls in all 500 ancestors) | 1609 | 53 | 92 | 85 | 290 (734,036) |
| chain-500, proposed diff | 771 | 9.1 | 9.0 | 11 | 27 (45,800) |

### M6. Dataflow graph micro-benchmarks (no kernel)

`python bench_dataflow.py SHAPE [--patch refs_index,disabled_counter]
[--reverse]`. CPU ms, min of 3; exponent from function calls where the work is
in Python calls, from CPU where it is in a C-level comprehension.

| | smoke-500 (251 cells) | smoke-2000 (1001) | chain-500 | chain-2000 | order |
| --- | ---: | ---: | ---: | ---: | --- |
| `register_cell` x all | 8.5 | **152** | 134 | **2829** | n^1.8 / n^2.0 |
| — with reference index + stale/disabled fast path | 1.7 | 6.9 | 4.0 | 13.3 | n^1.0 |
| `register_cell` x all, children registered before parents (`--reverse`), **with** the index + fast path | — | — | 86 (1000 cells: 454) | **3053** | **n^2.7** (CPU; `get_path` list copies) |
| `topological_sort(all)` | 0.25 | 2.0 | 0.39 | 4.5 | n |
| `topological_sort(1 cell)` | 0.011 | 0.05 | 0.02 | 0.09 | n (rebuilds registration order) |
| `Runner.compute_cells_to_run(all)` | 0.35 | 3.4 | 0.69 | 6.2 | n |
| `is_disabled` for every cell (done on every run) | 0.11 | 0.49 | 29.7 | **559** | n / n² |
| `descendants` for every cell (done on run-all) | 0.28 | 1.4 | 40.1 | **797** | n / n² |
| `variables` payload (done on every `mutate_graph`) | 0.04 | 0.14 | 7.8 | **131** | n / n² |
| `graph.set_stale({first})` | 0.00 | 0.00 | 0.25 | 1.0 | n |

### M7. Variants

- **No stdio redirection** (`--streams none`, isolates F2; unpaired,
  `m_smoke_none.jsonl`): smoke-500 run phase 489 → 300 ms CPU.
- **`auto_reload = "lazy"`** (`compare.py smoke 500 3 all prod lazy`):
  smoke-500 run phase **351 → 1,414 ms CPU**, calls 3.37M → 6.94M (F8).
- **gc**: 28 ms of a 1348 ms instantiate (55 gen-0, 5 gen-1, 0 gen-2
  collections; `micro_misc.py gc`) — not a factor.

## Findings (highest impact first)

### F1. With lazy startup (the default), every run request recompiles every pending cell and rebuilds a throwaway graph

- **Category:** caching, algorithms
- **Where:** `marimo/_runtime/runtime.py:2088` (`Kernel.prepare_execution_requests`):
  the loop at `:2133-2143` calls `compile_cell(request.code, …)` (`:2139`) for
  every request in `_pending_execution_requests`, ignoring the
  `_startup_cell_cache` that `_handle_markdown_cells_on_instantiate` filled with
  exactly those compiled cells (`:2859-2862`); then `:2145`
  `dataflow.get_ancestors_from_cells` (`marimo/_runtime/dataflow/__init__.py:75`)
  registers every cell into a fresh topology. `auto_instantiate` defaults to
  `False` (`marimo/_config/config_schema.py:139`).
- **Evidence:** MEASURED (M5). smoke-500: each single-cell run is **310–430 ms
  CPU** and 1.44M function calls, 247 of 251 `compile_cell` calls per request
  (cProfile: `prepare_execution_requests` 1.571 s of a 1.640 s run). smoke-2000:
  **2.0–3.6 s CPU per cell run**. The cost repeats on every request until the
  notebook has been fully run, so stepping through a notebook cell by cell is
  O(n²) compiles.
- **Why it is slow:** to find pending ancestors of the cell being run, the
  kernel needs the refs/defs of all pending cells; it obtains them by compiling
  them again, each time, and then pays the O(n²) graph build of F6 on top.
- **Proposed fix:** reuse the compiled `CellImpl` (it is only read):
  `StartupCellCache.peek(cell_id, code)` first, and `store` what had to be
  compiled so the eventual registration reuses it too (in the diff). Better
  still, keep one persistent "pending" topology updated as cells are
  registered/edited instead of rebuilding it per request.
- **Expected impact:** MEASURED with the diff: smoke-500 **~350 → 4–8 ms**
  (first run 32 ms), smoke-2000 **~2300 → 8–16 ms**; calls 1.44M → 17k. In the
  pytest benchmark (200 cells): 584,263 → 42,240 calls.
- **Effort / risk:** S. The cached cell is the object later registered; the
  analysis must stay read-only (it is today: `register_cell_dependencies` does
  not touch runtime state). Cells with syntax errors are still recompiled per
  run (cache holds `None`).

### F2. Every cell run creates 2 pipes and 2 threads, and blocks on both threads to exit

- **Category:** batching, lazy-init
- **Where:** `marimo/_runtime/runtime.py:913` (`_install_execution_context`) →
  `marimo/_runtime/redirect_streams.py:105-106` (`redirect(stdout)`,
  `redirect(stderr)`) → `marimo/_messaging/streams.py:730` (`redirect`):
  `os.dup`, `os.pipe`, `_NativePipe.start` (`:335`, a new `threading.Thread`
  per stream per cell), `os.dup2`; on exit `_NativePipe.finish` (`:380`) does a
  `FIONREAD` ioctl, builds a kqueue selector (`_pipe_at_eof`, `:306`) and
  `Condition.wait_for` until the reader thread has seen EOF and closed. The
  same context is entered for every UI-element update (`runtime.py:2549`),
  function call RPC (`:2744`) and pdb request (`:2257`).
- **Evidence:** MEASURED. `micro_redirect.py`: one empty execution context =
  **650 µs process CPU, 0.9–2.1 ms wall, 2.0 threads started**. In the real
  kernel subprocess profile it is **1.525 s of the 1.70 s run phase** at
  smoke-500 under load (`finish` 1.245 s over 502 calls = 2.5 ms each): the
  main thread sleeps until two freshly created threads get scheduled, twice per
  cell. `--streams none` removes 190 ms of 489 ms at smoke-500.
- **Why it is slow:** ~30 syscalls and two thread create/wake/join handoffs per
  cell to capture native (C-level) writes, for cells that write nothing. Thread
  handoffs are the first thing to degrade when the machine is busy — e.g. while
  the browser is rendering 500 cells.
- **Proposed fix:** keep one pipe + one reader thread per std stream for the
  kernel's lifetime; per cell only re-point it (`pipe.cell_id = …`, two `dup2`,
  one flush, one `FIONREAD` drain). Prototype: `apply_redirect_reuse` in
  `patches.py` (40 lines). Alternative with less risk: install the redirect once
  per *run* (in `Runner.run_all`) and only switch attribution per cell.
- **Expected impact:** MEASURED with the prototype: **650 → 29 µs CPU, ~1 ms →
  31–47 µs wall per cell**, 0 threads per cell; -115k calls at smoke-500.
  ~160 ms CPU (more in wall) off a 252-cell run-all, ~0.6 ms off every slider
  event.
- **Effort / risk:** M. Attribution of late native writes (a subprocess still
  writing after its cell finished) changes from "the cell that opened the pipe"
  to "the cell current when the bytes are read" unless the reader is drained at
  each switch (the prototype drains `FIONREAD` bytes on exit); nested
  redirects (code mode running cells inside the scratchpad) must keep the
  current path; inheritable-fd semantics for child processes must be preserved.
  Not in the diff for that reason; the stream tests
  (`tests/_messaging`, `tests/_runtime/test_redirect_streams.py`) are the gate.

### F3. A duckdb hook searches the import path and re-parses every cell after it runs

- **Category:** caching, lazy-init
- **Where:** `marimo/_runtime/runner/hooks_post_execution.py:177`
  (`_broadcast_duckdb_datasource`): `:186` `DependencyManager.duckdb.has()` →
  `importlib.util.find_spec` on every cell
  (`marimo/_dependencies/dependencies.py:25-28`); `:190` `cell.sqls` →
  `marimo/_ast/cell.py:259` (`_get_sqls`) → `ast_parse(self.code)` (`:262`) and
  a full `SQLVisitor` walk, although `CellImpl.mod` already holds the parsed
  module.
- **Evidence:** MEASURED. `cell._get_sqls()` **300 µs per code cell**
  (`micro_units.py`); `duckdb.has()` 34–49 µs, **241 µs CPU when `""` is on
  `sys.path`** (unnamed notebook, `runtime.py:688`: each `find_spec` then calls
  `os.getcwd()`). Ablation at smoke-500: gating the hook removes **665k of
  3.376M function calls (20%)**. Real kernel profile: 0.333 s of the 1.70 s run
  phase. Only fires when duckdb is installed — it is a marimo `sql` extra and
  was in this venv.
- **Why it is slow:** a third parse of the cell (after two in `compile_cell`)
  plus a visitor pass, to answer "did this cell modify the in-memory duckdb
  catalog?" for cells that contain no SQL, in a process that has not imported
  duckdb.
- **Proposed fix:** (a) use `DependencyManager.duckdb.imported()` — if duckdb
  is not in `sys.modules`, no cell has touched it; (b) in `_get_sqls`, return
  `[]` when neither `"sql"` nor `"execute"` occurs in the source and otherwise
  visit `self.mod` instead of re-parsing (both in the diff). Longer term have
  `ScopedVisitor` record SQL strings during the compile pass it already makes.
- **Expected impact:** ~340 µs per code cell: **~85 ms CPU at smoke-500, ~340 ms
  at smoke-2000**; -20% function calls.
- **Effort / risk:** S. (a) changes behaviour only for `mo.sql(…, engine=other)`
  in a process that never imported duckdb, where there is nothing to broadcast.
  (b) the textual prefilter is exact for ASCII identifiers; a fullwidth
  `ｓｑｌ` attribute would be missed (NFKC-normalise first if that matters).

### F4. Every run rescans the entry points of every installed distribution

- **Category:** caching
- **Where:** `marimo/_runtime/runner/cell_runner.py:249`
  (`Runner.__init__`: `executor=resolve_executor()`) →
  `marimo/_runtime/executor/evaluator.py:162-167` →
  `marimo/_entrypoints/registry.py:100` (`EntryPointRegistry.names`) → `:155-156`
  (`get_entry_points` → `importlib.metadata.entry_points()`). A `Runner` is
  built for every `_run_cells_internal` (`runtime.py:1903`), including each
  iteration of the state-update loop (`:1603`) and the scratchpad (`:2337`).
- **Evidence:** MEASURED. `micro_fixed.py`: **6.5 ms CPU, 10.7 ms wall (min),
  17,753 function calls, 67 `open()` + 2 `listdir`** per call in this venv
  (67 distributions; a data-science environment has several hundred, and the
  cost is linear in that). It is 82% of an empty run at smoke-500 (21,543
  calls / 7.0 ms → 1,891 calls / 0.5 ms with it cached). Under cProfile + load
  it showed as 62 ms per run.
- **Why it is slow:** a filesystem scan of all `*.dist-info/entry_points.txt`
  to discover an optional executor plugin, repeated for every cell run, slider
  drag and state update.
- **Proposed fix:** resolve once per kernel and pass it to `Runner`
  (`executor: Executor | None = None`; in the diff). Caching inside
  `EntryPointRegistry` instead would break `tests/test_entrypoints.py`, which
  patches `get_entry_points` and mutates `_plugins` between calls.
- **Expected impact:** **-6.5 ms CPU (≥10 ms wall) on every run**; single-cell
  operations on smoke-500 go 9–11 → 1–2.6 ms with the other fixes (M4).
- **Effort / risk:** S. An executor plugin installed mid-session is picked up
  after a kernel restart (invalidate from the package-install callback if that
  matters).

### F5. `_invalidate_cell_state` scans every cell's imports twice per cell, for a check that can never fire

- **Category:** algorithms
- **Where:** `marimo/_runtime/runtime.py:1262` and `:1274`
  (`_invalidate_cell_state`) → `marimo/_runtime/packages/module_registry.py:44`
  (`modules`, iterates all cells; `CellImpl.imported_namespaces`
  `marimo/_ast/cell.py:307` rebuilds a list and a set per cell per call) and
  `:52` (`missing_modules`). Called for every cell to run
  (`invalidate_state`, `runtime.py:1866`) and for every deactivated cell.
- **Evidence:** MEASURED. `modules()` 48 µs/call at 251 cells, 170 µs at 1001;
  twice per cell → **24 ms at smoke-500, 341 ms at smoke-2000**
  (`micro_units.py`); pyinstrument at smoke-2000: `invalidate_state` 0.75 s of
  a 2.35 s run phase; ablation: -381k calls at smoke-500, **-2.0M of 9.5M at
  chain-500**. And it is dead: the graph is not mutated between the "before"
  and "after" reads (deletion happens later, in `_deactivate_cell`), so
  `missing_after == missing_before` always. Verified: deleting the only cell
  that imports a missing module produces **zero**
  `send_missing_packages_alert` calls.
- **Why it is slow:** an O(n) scan, done 2n times per run-all, whose two
  results are compared with each other.
- **Proposed fix:** remove it from `_invalidate_cell_state`; compute
  before/after once in `mutate_graph` around the register/delete loop, which is
  also where it becomes correct (in the diff). `ModuleRegistry` could keep a
  `Counter` of namespaces updated on register/delete to make it O(1).
- **Expected impact:** O(n²) → O(n) per run: -24 ms at 500, **-341 ms at 2000**
  (smoke); restores the "missing packages shrink after delete" alert.
- **Effort / risk:** S. Behaviour change: the frontend now *does* receive the
  shrunken `MissingPackageAlertNotification` after a deletion (the documented
  intent at `marimo/_runtime/callbacks/packages.py:140`).

### F6. Registering cells is quadratic (cubic when children are registered before parents)

- **Category:** datastructures, algorithms
- **Where:** `marimo/_runtime/dataflow/edges.py:44` (`get_referring_cells`,
  `:89` scans every cell per name), called from `compute_edges_for_cell`
  (`:217`) once per definition (`:249`), once per **reference** for the
  "who deletes this name" check (`:287-293`, which iterates every referrer of
  e.g. `json`), and once per deleted ref (`:299`).
  `marimo/_runtime/dataflow/graph.py:115-119` (`register_cell`) then computes
  the full ancestor closure twice (`is_any_ancestor_stale` `:121`,
  `is_any_ancestor_disabled` `:127`).
  `marimo/_runtime/dataflow/topology.py:136-159` (`get_path`, used by
  `CycleTracker.detect_cycle_for_edge`) copies the path list for every node it
  visits (`:153`).
- **Evidence:** MEASURED (M6). Graph only: smoke-2000 **152 ms** (n^1.8),
  chain-2000 **2829 ms** (n^2.0); in the kernel `mutate_graph` is 113–129 ms
  (smoke-2000) and **2.4–2.8 s** (chain-2000). Reverse-order chain: 13.6 → 86 →
  454 → **3053 ms** for 250 → 2000 cells (n^2.7) from the path copying alone.
- **Why it is slow:** a list-of-cells scan where a `name → cells` index is
  needed; full transitive closures materialised to answer "is any ancestor
  stale/disabled" (almost always "no"); BFS that copies its path per node.
- **Proposed fix:** (1) `MutableGraphTopology` keeps `_referring` and
  `_deleting: dict[Name, set[CellId_t]]`, maintained in `add_node` /
  `remove_node`; `get_referring_cells(…, "python")` and the deleter check become
  lookups (in the diff). (2) Early-exit ancestor walk (in the diff), and the
  real fix: make the graph the owner of "stale" and "disabled" sets (or
  counters) so the common "nothing is stale/disabled" case is O(1)
  (prototype `apply_disabled_counter`). (3) `get_path`: BFS with parent
  pointers, build the path once on success.
- **Expected impact:** MEASURED with prototypes (1)+(2): smoke-2000 152 → 6.9 ms,
  chain-2000 **2829 → 13.3 ms**, linear; kernel `mutate_graph` chain-2000
  **2,783 → 36 ms**, smoke-2000 129 → 15 ms. `variables` payload (F7) falls out of the same index.
- **Effort / risk:** S for the index (SQL references keep the scan), M for the
  stale/disabled ownership change (many direct `cell.set_stale` callers).

### F7. Touching one cell does whole-graph work: per-cell `is_disabled` walks, per-cell `descendants`, and a full `variables` rebuild

- **Category:** algorithms, batching
- **Where:**
  - `marimo/_runtime/runtime.py:1596-1602` (`_run_cells`): `is_disabled(cid)`
    for **every cell in the graph on every run**, evaluated before the cheap
    `run_result_status` test; `is_disabled`
    (`marimo/_runtime/dataflow/graph.py:221`) walks all ancestors.
  - `marimo/_runtime/runner/hooks_preparation.py:24` and
    `marimo/_runtime/runner/cell_runner.py:1035`: `is_disabled` again per cell to
    run.
  - `marimo/_runtime/runtime.py:1286-1289` (`_invalidate_cell_state`): full
    `descendants()` closure per cell to run, to dispose lifecycle items that
    are almost always already being disposed.
  - `marimo/_runtime/runtime.py:1535-1551` (`mutate_graph`): the
    `VariablesNotification` calls `get_referring_cells` for every definition
    (O(defs·cells)) and is sent in full on every graph mutation.
  - `marimo/_runtime/runner/hooks_pre_execution.py:17-25` (`_set_staleness`,
    lazy mode only): `is_any_ancestor_stale` — a full ancestor closure — before
    every cell (its own TODO notes the check is redundant when parents run
    first).
  - smaller O(n)-per-run items: `all_temporaries`
    (`cell_runner.py:901-907`), `topological_sort` rebuilding the registration
    index (`marimo/_runtime/dataflow/__init__.py:143`), `set(self.graph.cells)`
    copies in `mutate_graph` (`runtime.py:1360`, `:1407`).
- **Evidence:** MEASURED (M4, M6). chain-500: empty run 646k calls / 25 ms,
  any single-cell op 30–60 ms; chain-2000: **empty run 10.0M calls / 525 ms**,
  single-cell ops 0.7–1.5 s CPU, and each sends a **121 KB** `variables`
  message. `is_disabled` for all cells: 559 ms at chain-2000; `variables`
  payload 131 ms. Star notebooks pay only the O(n) part (0.5 ms + 16 KB at
  2000).
- **Why it is slow:** per-cell questions asked by walking the graph from each
  cell, instead of one traversal per run; and a full snapshot broadcast where a
  delta (or nothing — the graph did not change on a re-run) would do.
- **Proposed fix:** `DirectedGraph.disabled_cells()` — one closure from the
  directly disabled cells (empty in O(n) when none are) used by all three call
  sites; dispose descendants once per run from the union closure; build
  `variables` from the reference index and skip the broadcast when the
  definitions/referrers did not change (hash the payload, or track a graph
  version); send per-variable deltas later. First three are in the diff.
- **Expected impact:** MEASURED with the diff/prototypes: chain-500 empty run
  25 → 0.5 ms (646k → 3k calls), single-cell ops **32 → 2.7 ms**; pytest
  benchmark chain-200 run-one-leaf 140,446 → 8,407 calls. Skipping unchanged
  `variables`: -3.7 KB (smoke-500) to -121 KB (chain-2000) per run request.
- **Effort / risk:** S–M. `disabled_cells()` is semantically identical to
  `{c for c in cells if is_disabled(c)}`. Disposal order changes (descendants
  after, rather than interleaved with, the cells being run).

### F8. With auto-reload on, every cell entry scans all of `sys.modules` and stats every user module

- **Category:** batching, caching
- **Where:** `marimo/_runtime/reload/manager.py:100` (`cell_scope`):
  `set(sys.modules)` (`:106`), `self._reloader.check(modules=sys.modules,
  reload=True, skip_non_user_modules=True)` (`:112-114`), and a second
  `set(sys.modules)` on exit; `marimo/_runtime/reload/autoreload.py:349-395`
  (`_check`) loops over every module (`:367`) and `os.stat`s each module that is
  not under stdlib/site-packages. Off by default (`auto_reload = "off"`).
- **Evidence:** MEASURED. `micro_autoreload.py`: `cell_scope()` = **302 µs per
  cell** with 993 modules loaded and no user modules, **2677 µs per cell** with
  538 user modules (an editable install — here marimo itself; any user with a
  large local package is in this case). smoke-500 run phase **351 → 1,414 ms
  CPU**, calls 3.37M → 6.94M (M1 table, last row vs the smoke-500 row).
- **Why it is slow:** O(#modules) Python loop + one `stat` per user module, per
  cell, although a background `ModuleWatcher` already polls the same files
  every second.
- **Proposed fix:** scan once per run (a preparation hook), or rate-limit the
  entry scan (prototype `apply_autoreload_coalesce`: at most every 250 ms);
  only classify module names not seen before; on exit diff `sys.modules` only
  when its length changed.
- **Expected impact:** MEASURED: the coalescing prototype alone takes the
  smoke-500 run phase with auto-reload from **1,441 → 574 ms CPU** (single
  runs, unnamed-notebook harness), i.e. back to the auto-reload-off level;
  with all prototypes 1,414 → 66 ms.
- **Effort / risk:** S–M. A file saved *during* a run is picked up by the next
  run (or 250 ms later) instead of by the next cell.

### F9. `_store_state_reference` builds the union of every definition and every temporary, per cell

- **Category:** algorithms
- **Where:** `marimo/_runtime/runner/hooks_post_execution.py:268-280`:
  `set(ctx.graph.definitions.keys()) | ctx.all_temporaries` at `:279`, passed to
  `StateRegistry.retain_active_states` (`marimo/_runtime/state.py:100`), which
  iterates `self._states` — empty unless the notebook uses `mo.state`.
- **Evidence:** MEASURED. 21 µs per cell at smoke-500 (1,850 temporaries),
  **111 µs per cell at smoke-2000** (7,677) → 5 ms and **111 ms** per run-all
  (`micro_units.py`); 0.156 s in the smoke-2000 pyinstrument tree.
- **Why it is slow:** an O(total names) set is allocated to filter a registry
  that is usually empty.
- **Proposed fix:** pass a predicate (`name in definitions or name in
  temporaries`) so the cost is O(#states) (in the diff), or return early when
  the registry is empty.
- **Expected impact:** O(n²) → O(n): -111 ms at smoke-2000.
- **Effort / risk:** S.

### F10. 8 notifications per cell, and the kernel echoes the whole notebook source back

- **Category:** batching, compression
- **Where:** `marimo/_runtime/execution.py:48-72` (`ExecutionAttempt.plan`,
  `code=… code` at `:65`), `:81`/`:89` (`running`, `completed`);
  `marimo/_messaging/notification_utils.py:204-219` (`broadcast_status`);
  `marimo/_runtime/runner/hooks_post_execution.py:346` (output broadcast, sent
  even when the output is empty and was empty before);
  `marimo/_runtime/runtime.py:1290` (`RemoveUIElementsNotification` per cell);
  `:1766` + `:1791` (`_publish_bindings` then `_publish_variable_previews`: two
  `variable-values` messages per defined variable, the first with
  `value: null`).
- **Evidence:** MEASURED (M3). smoke-500: 3,011 messages / 1.17 MB.
  `execution[planned]` carries the cell source: **523 KB of 1,172 KB (45%)**;
  dropping `code` from it leaves 809 KB (`micro_misc.py echo 500
  no_code_echo`). Kernel-side cost per message is small (2.3 µs to build +
  serialize; ~48 µs per `send_bytes` in the real kernel) — the cost is on the
  wire and in the frontend, which must process 8 state transitions per cell.
- **Why it is slow:** each lifecycle step is its own message with its own
  `run_id`/`execution_id`/timestamp envelope (~180–260 bytes, ~100 of them
  `null` fields); several pairs are always emitted back-to-back.
- **Proposed fix (coalescing candidates, by pair):**
  1. `execution: running` + `cell-op status=running, console=[]` (adjacent,
     same ids) → one message.
  2. `cell-op output` (empty) + `cell-op status=idle` + `execution: completed`
     → one message; the markdown fast path already sends idle+output together.
     Skip the empty-output message when the cell had no output before.
  3. `remove-ui-elements` only when the cell registered UI elements.
  4. `variable-values`: send once, after the preview is computed (or send the
     preview lazily when the variables panel is open).
  5. `planned`: send `code_fingerprint` only; the frontend already has the
     source it sent (send `code` only when the kernel's source differs).
  6. `omit_defaults` on the notification structs to drop the `null` fields.
- **Expected impact:** 8 → 3–4 messages per cell; smoke-500 1.17 MB → ~0.5 MB
  (-31% from (5) alone, MEASURED; the rest INFERRED from the per-message sizes
  in M3).
- **Effort / risk:** M–L; protocol change that the frontend/session view must
  follow. Coordinate with the wire-protocol findings.

### F11. Startup compiles every cell before the first output, and parses each cell four times

- **Category:** lazy-init, streaming
- **Where:** `marimo/_runtime/runtime.py:2852-2862`
  (`_handle_markdown_cells_on_instantiate`: compile loop over all cells) then
  `:2884-2904` (markdown render + broadcast loop).
  `marimo/_ast/compiler.py:248` and `:284` (`module_compile(code)` twice),
  `marimo/_ast/cell.py:262` (F3), `marimo/_core/code.py:18` (fingerprint).
- **Evidence:** MEASURED. compile + markdown is 308–384 ms CPU of 670–921 ms at
  smoke-500 (pyinstrument: `compile_cell` 306 ms, `md()` 152 ms incl. 79 ms
  one-time `Markdown.__init__`), i.e. ~0.65 ms per cell, and it is all spent
  before the first `cell-op` leaves the kernel (real server, kernel under
  cProfile and load: first output 866 ms after kernel-ready). After the other
  fixes it is **84% of instantiate**.
- **Why it is slow:** eager whole-notebook compile to decide which cells are
  markdown; no output can stream until it finishes.
- **Proposed fix:** render each markdown cell as soon as it is compiled (the
  setup cell that exports `mo` is first in file order; fall back to today's
  behaviour otherwise); see the load/save report for the compile cost itself.
- **Expected impact:** first markdown output after ~1 ms instead of ~300 ms at
  500 cells; total unchanged.
- **Effort / risk:** S–M.

### F12. Paper cuts (each small, all per cell or per run)

- **`_flush_console` thread round trip per cell** — `hooks_post_execution.py:486`
  → `streams.py:215-256`: a `FlushMarker` is queued and the main thread waits
  for the console writer thread, even when nothing was written. ~50 µs CPU,
  0.5 ms per cell under load (0.132 s / 251 cells in a loaded profile).
  MEASURED. Fix: skip when no console message was queued since the last flush
  (prototype `apply_flush_skip`). S.
- **Tracing decorators on the runner hooks** — `marimo/_tracer.py:71-82`:
  `MockTracer.start_as_current_span` re-creates a generator context manager per
  call; 4,022 `contextlib.inner` calls per smoke-500 run (16 per cell). ~1–3 µs
  each.
  MEASURED (count). Fix: return the function unchanged when tracing is off. S.
- **`can_narwhalify` on every defined value** — `marimo/_data/get_datasets.py:40`
  → `marimo/_utils/narwhals_utils.py:67`: `nw.from_native(5)` raises through 12
  type probes, 12–16 µs per variable (`micro_values.py`). MEASURED. Fix: skip
  builtin scalars/containers. S.
- **`get_multiply_defined` sorts all definitions on every `mutate_graph`** —
  `marimo/_runtime/dataflow/definitions.py:188`: filter `len(definers) > 1`
  before sorting. INFERRED. S.
- **`run_hooks = self._hooks.copy()` + four `add_*` + re-sort per run** —
  `runtime.py:1891-1895`. INFERRED (not visible in profiles).
- **Unnamed notebooks put `""` on `sys.path`** — `runtime.py:688`: every
  `importlib.util.find_spec` then calls `os.getcwd()`; `duckdb.has()` 49 → 241
  µs CPU, and milliseconds of wall under load. MEASURED. Fix: insert the
  resolved cwd.
- **`mount_lens` retries a failing import** — `hooks_lens.py:28`: only for
  cells that import `marimo`, so once per run here. INFERRED, negligible.
- **`used_by`/`declared_by` order is non-deterministic** — `runtime.py:1541-1546`
  (`list(set)`): the same graph serialises differently run to run, which
  defeats any payload hashing/deduplication (seen in `check_parity.py`).
  MEASURED. Fix: sort.

### F13. (INFERRED) In `--sandbox`, every registered cell with a new import can spawn `uv tree` and re-read the notebook

- **Category:** batching, caching
- **Where:** `marimo/_runtime/runtime.py:1128-1139` (`_maybe_register_cell`
  calls `update_script_metadata` per registered cell) →
  `marimo/_runtime/packages/sandbox_package_manager.py:139` →
  `marimo/_environments/sandbox.py:452` (`record_dependencies`): `:471`
  `_declared_dependencies()` re-reads and parses the notebook file, `:477`
  `self.packages()` → `marimo/_environments/backends.py:400` runs
  `uv tree --script`. Non-sandbox uv projects:
  `marimo/_runtime/packages/pypi_package_manager.py:534` (`_get_version_map` →
  `uv tree` / `uv pip list`) per cell.
- **Evidence:** INFERRED from code; not measured (needs a uv sandbox and
  network). It does **not** affect the smoke notebook's code cells: their
  imports are underscore-private, which `compile_cell` keeps out of
  `variable_data`, so `imported_namespaces` is empty (verified on the fixture).
  It applies to notebooks where many cells import public modules.
- **Proposed fix:** collect the namespaces for the whole `mutate_graph` batch
  and update the script metadata once.
- **Expected impact:** one subprocess per batch instead of one per importing
  cell.
- **Effort / risk:** S.

## Ruled out

- **Notification construction/serialization in the kernel**: 0.29 µs to
  serialize, 2.3 µs to build + broadcast a `cell-op` (`micro_misc.py notify`);
  3,011 messages ≈ 7 ms. (The real pipe `send_bytes` is ~48 µs/message under
  load; batching would help there, see F10.)
- **O(n²) bytes during run-all**: none; bytes exponent 0.99–1.01 for all shapes.
- **gc**: 28 ms of 1348 ms; no gen-2 collection during a 500-cell run.
- **`topological_sort` / `compute_cells_to_run`**: 2.0 / 3.4 ms at smoke-2000,
  linear.
- **Cycle detection for cells registered in dependency order**: O(1) per edge
  (new cell has no children). Only the reverse order is pathological (F6).
- **Lazy-mode staleness propagation**: `graph.set_stale` 1.0 ms on a 2000-chain.
- **Locks** (`graph.lock`, `_state_lock`, `stream_lock`): uncontended; 6,023
  `lock.acquire` calls, 11 ms total (including waits) in a profiled smoke-500
  run.
- **`_bind_variables` / `_read_inputs`**: 56 / 96 µs per cell *under cProfile*
  (0.014 s and 0.024 s cumulative over 251 cells); no scaling with notebook
  size.
- **Signal handling** (`SigintHandler.defer` per stream write): inside the
  2.3 µs per message above.
- **The prototypes do not drop console output**: UI-callback console messages
  are flushed by the 10 ms writer timer and can land after the call returns;
  with a 0.3 s wait both variants deliver the same 2 messages.

## Benchmarks added

- `tests/_runtime/test_large_notebook.py` — one parametrized test
  (`smoke`, `outputs`, `chain`) that generates 50- and 200-cell notebooks with
  `scripts/benchmarks/generate_large_notebook.py`, drives a real kernel
  (`mocked_kernel_session`) through run-all, a single-leaf run, and a
  single-leaf run under lazy startup, asserts correctness (every cell reaches
  `idle`, all graph cells `success`, fixed message count per cell) and
  **generous growth-order bounds on deterministic counters** (function calls,
  emitted bytes) — no timings. `-s` prints the measurements. 3 passed in
  ~19 s on the loaded machine; counts are identical run to run.
  - Today (200 cells): smoke run-all 1.45M calls, run-leaf 40k,
    run-leaf-while-pending **584k**; chain run-all 1.86M, run-leaf 140k.
  - With the proposed diff: 1.10M / 10.9k / **42k**; chain 0.60M / 8.4k.
  - **`.venv` has no `pytest`** (`.venv/bin/python -m pytest` →
    `No module named pytest`), so I could not run the exact command from the
    brief. I ran it with a throwaway venv in my scratch dir
    (`uv pip install -e . --group test`):
    `.context/perf/backend-runtime/venv-test/bin/python -m pytest tests/_runtime/test_large_notebook.py -q`.
    I did not modify the shared `.venv`.
- Scratch harness for re-runs: `.context/perf/backend-runtime/` (see Method).

## Could not measure

- Quiet-machine wall-clock (load average never dropped below ~30); treat
  absolute ms as upper bounds and rely on calls / ratios.
- F13 (sandbox mode), Windows (no fd-redirect differences measured), run mode
  (thread-local stdio proxy instead of `dup2`), and the frontend-side benefit of
  fewer notifications (F10).
- Side observation, not perf: `--profile-dir` breaks shutdown —
  `marimo/_session/managers/kernel.py:342` passes extra positional args to
  `print_`, raising `AttributeError: 'str' object has no attribute 'write'`;
  the server then had to be killed (the kernel profile was still written).
