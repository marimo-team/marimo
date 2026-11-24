# marimo large-notebook performance: findings and task list

Nov 24, 2026 · @Myles Scolnick

## Summary

A 500-cell notebook needs about 6 minutes of browser main-thread work to finish loading and 0.6–0.9 s of work per keystroke, and almost all of it comes from a few mechanisms that scale with the square of the cell count. Six small frontend fixes cut load to 49 s and typing to 76 ms per key in a prototype build.

Where the time goes, largest first:

1. **Load is style recalculation (72–74%).** Each of the 501 editor mounts rewrites CodeMirror's stylesheet and restyles thousands of animated placeholder bars. Fixes: E1, B1, B2.
2. **Typing re-renders every cell.** Every cell subscribes to the document-sync status and the layout object changes identity on each keystroke; each render then scans the whole DOM. Fixes: S4, S6, S3.
3. **Run-all recomputes every cell on every kernel event.** The WebSocket handler takes 27 s for a 500-cell load. Fixes: S1, S2.
4. **The server does whole-notebook work per edit and save.** An edit re-fingerprints every cell (116 ms of event-loop CPU) and a save recompiles every cell (0.9–1.5 s). Fixes: W1, W2, L1.
5. **The kernel adds 1.4–2.3 ms around each 14 µs cell.** With the default lazy startup, running one cell recompiles every pending cell (310–430 ms). Fixes: K1–K5.

Network traffic is not the problem: it is linear in cell count and already compressed. The sections below hold 71 tasks with file locations, evidence and effort; the task list near the end puts them in order.

## How it was measured

Every number comes from generated notebooks that copy the shape of the slow one; the original was only parsed for statistics, never run.

| Property of the slow notebook | Value |
| --- | --- |
| Cells | 521 (plus one `app.setup` cell) |
| Size | 16,981 lines, 625 KB |
| Markdown cells | 269, of which 268 are `hide_code=True` |
| Code cells | 252 named cells; median 32 lines, p90 75, max 143 |
| Dependencies | No cell takes args or returns values: a star around the setup cell |
| Outputs | Code cells mostly end in `assert`; output comes from the markdown cells |

The generator is `scripts/benchmarks/generate_large_notebook.py OUT.py --cells N --shape smoke|outputs|chain`.

| Shape | What it stresses |
| --- | --- |
| `smoke` | Mirrors the slow notebook: alternating hidden markdown and assert-only code cells |
| `outputs` | Same, but every code cell renders an output (markdown, dict, slider, table, accordion, stat, stdout, list) |
| `chain` | A linear dependency chain, `v_i = v_{i-1} + 1` |

Each shape was generated at 50, 100, 250, 500, 1,000 and 2,000 cells into a scratch directory. Timings are medians of repeated runs on an Apple M4 Max; scaling curves matter more than absolute values because several benchmarks ran at once.

Benchmarks and tests added on this branch:

| File | What it does |
| --- | --- |
| `tests/_ast/test_large_notebook_perf.py` | Load and save round-trip on generated notebooks; asserts growth of function-call counts, not timings |
| `tests/_runtime/test_large_notebook.py` | Run-all, single-leaf run and lazy-startup run in a real kernel; asserts call-count and byte growth |
| `frontend/benchmarks/large-notebook-state.bench.ts` | Store cost of load, typing, kernel events and selectors at 500 and 2,000 cells, per-event against batched |
| `frontend/benchmarks/large-notebook-editor.bench.ts` | Editor creation, reconfigure and language detection at 50 and 500 cells |
| `frontend/benchmarks/notebook-load.browser.ts` | Load timing in Chromium for any notebook URL |
| `frontend/benchmarks/create-editing-fixtures.ts` | New `--cells=25,100,250,500` option; documented in `cell-editing.md` |
| `scripts/benchmarks/ws_traffic.py` | Connects like the editor and prints frames and bytes per event kind |

The two pytest files pass (5 tests) and the frontend files typecheck. The full per-area reports are in [`reports/`](reports/), with 21 unapplied patches in [`patches/`](patches/). The reports also name scratch scripts under `.context/perf/<area>/`; those are not on this branch.

## Browser measurements

At 500 cells the editor needs 352–386 s of main-thread work to finish loading and 0.6–0.9 s of work per keystroke; six small fixes prototyped at build time cut that to 49 s and 76 ms. Measured in Chromium 156 headless against the production build: cold kernel start plus run-all, `smoke` shape, no CPU throttle, median of 2–3 runs.

| Load metric | 25 cells | 100 cells | 250 cells | 500 cells | Exponent, 100 to 500 |
| --- | --- | --- | --- | --- | --- |
| All cells in the DOM | 3.3 s | 4.8 s | 5.1 s | 6.6 s | 0.19 |
| Run-all complete | 3.9 s | 6.8 s | 17.1 s | 64.6 s | 1.38 |
| All editors mounted | 4.7 s | 17.4 s | 86.8 s | 356.6 s | 1.87 |
| Main-thread task time | 1.9 s | 13.4 s | 83.6 s | 352.4 s | 2.03 |
| Style recalculation | 0.8 s | 9.5 s | 63.2 s | 259.9 s | 2.05 |
| Script | 0.8 s | 2.7 s | 13.2 s | 58.0 s | 1.89 |
| DOM elements | 5,201 | 18,758 | 45,971 | 91,027 | Linear |
| Event listeners | 4,849 | 17,430 | 42,927 | 85,294 | Linear |
| JS heap after GC | 51 MB | 115 MB | 245 MB | 458 MB | Linear |

A 1,000-cell notebook was still loading when stopped after 52 minutes. With 4× CPU slowdown, 250 cells keep the main thread busy for 9.5 minutes and 500 cells had not finished run-all after 10 minutes. Of the 501 editors built, 3 are in the viewport and 250 belong to hidden markdown cells.

Where the CPU goes at 500 cells, from profiles of an unminified build:

- **Load:** 49% inside the `EditorView` constructor, which forces a document-wide style recalculation per editor; 34% style, layout and paint outside script.
- **Typing:** 29% React render and commit, 28% `isInVscodeExtension()`. One keystroke causes 6.9 commits and 47,750 component renders.
- **Run-all:** 46.5% in the WebSocket handler and the Jotai recompute it triggers.

| At 500 cells | Production build | Prototype build (E1, B1, B2, S3, S4, S6) |
| --- | --- | --- |
| Load: all editors mounted | 393 s | 54.8 s |
| Load: main-thread task time | 385.9 s | 48.9 s |
| Load: style recalculation | 276.6 s | 4.3 s |
| Load: script | 69.0 s | 38.4 s, of which 26.2 s is the WebSocket handler |
| Typing: work per key | 577 ms | 76 ms |
| Typing: key to paint, p95 | 1,659 ms | 57 ms |
| Create cell | 3,962 ms | 658 ms |
| Move cell down (work) | 6,382 ms | 642 ms |
| Hide code | 1,699 ms | 526 ms |
| Run one cell | 1,403 ms | 898 ms |
| Delete cell | 1,424 ms | 1,337 ms |

Other interactions on the production build at 500 cells: an arrow key in command mode 1.9 s, opening find 8.9 s, opening the command palette 1.9 s, and scrolling at 10 fps.

| ID | Task | Where | Evidence | Expected impact | Effort |
| --- | --- | --- | --- | --- | --- |
| B1 | Make `style-mod` skip writing an unchanged sheet (`pnpm patch`, then upstream); ship with E1 | `style-mod` `StyleSet.mount`, reached from every `EditorView` constructor | 266 ms of forced style recalculation per editor mount at 250 cells; sharing themes alone (E1) changes nothing | 250-cell load 95.6 → 24.3 s; style 70.4 → 4.3 s (measured) | S |
| B2 | Remove the pulse animation from code placeholder bars | `components/editor/cell/code/code-placeholder.tsx:37`, `components/ui/skeleton.tsx:10` | \~16 animated bars per unmounted cell, \~8,000 at the start of a 500-cell load; every sheet rewrite invalidates all of them | 500-cell load 385.9 → 164.0 s on its own (measured with one injected CSS rule) | S |
| B3 | Return the same state from pending-delete `clear`; subscribe per cell | `core/cells/pending-delete-service.ts:120`, `components/editor/navigation/navigation.ts:224` | Each selection change hands every cell a new object: 90,819 renders for 6 arrow keys at 250 cells | Arrow-key navigation independent of cell count (estimate; patch saved, not validated in a build) | S |
| B4 | Notebook-wide find: search the document text once and highlight only visible editors | `core/codemirror/find-replace/search-highlight.ts:21`, `components/find-replace/find-replace.tsx:60` | Opening find dispatches to every editor and forces an 8.3 s layout; 1.1 s of work per query key | Open under 200 ms, typing under 100 ms per key (estimate) | M |
| B5 | Find and remove the document-wide restyle when a dialog opens | `components/editor/controls/command-palette.tsx:37`, `css/globals.css:135` | 1,428 ms of style recalculation on Mod-K; the triggering attribute change is not yet identified | Palette open under 300 ms (estimate) | S–M |
| B6 | Re-measure scroll and resize once editors are lazy (E2) | CodeMirror scroll listeners on 13 ancestors per editor | Scrolling costs 6.2 s of main-thread time per 6 s of wheel events | Not quantified | M |

Chromium results for tasks listed in other sections:

| Task | Result in Chromium |
| --- | --- |
| S4 | Typing at 250 cells 323 → 88 ms of work per key on its own |
| S6 | 88 → 53 ms per key on top of S4 |
| S3 | 29.8 s of 105.9 s while typing 30 characters at 500 cells |
| S1, S2 | Not prototyped; the largest cost left after the six fixes |
| S8 | `useCellActions` is 7.2% of typing CPU and retains 18 MB of a 109 MB heap at 100 cells |
| E8 | `ConsoleOutput`'s layout effect is 3.8 s of self time during a 500-cell load |
| E10 | `content-visibility: auto` on cells cut 500-cell load from 385.9 to 93.1 s, but it clips hover actions and does not help typing. Selector matching is only 3–4% of style time |

## Backend load and save

Opening a 500-cell notebook parses the file 4 times and compiles every cell 5 times, and every save recompiles all cells whether or not anything changed. Load times are calm wall-clock; save and prototype figures are process CPU under contention, about 1.5–2× high, so use the ratios.

| Measure, `smoke` shape | 500 cells | 2,000 cells |
| --- | --- | --- |
| `ast.parse` of the whole file (reference) | 37 ms | 178 ms |
| `parse_notebook` | 182 ms | 1,042 ms |
| `load_app` (parse + compile + register) | 388 ms | 1,939 ms |
| Save through the bridge, one cell edited | 463 ms | 1,714 ms |
| Same save with compile cache, parse skip and fingerprint cache | \~30 ms (sum of measured parts) | \~110 ms (sum of measured parts) |
| `marimo check` (CPU, includes 0.8 s startup) | 2.5 s | 8.0 s |
| `python notebook.py` (CPU, includes 0.6 s import) | 1.9 s | 5.6 s |

Counted in a live `marimo edit` session at 500 cells: 4 `parse_notebook` calls, 3 `load_app` calls, 2,004 server-side `compile_cell` calls plus 501 in the kernel, and 2,004 `code_fingerprint` calls. The server process never executes a cell. Graph build is the quadratic part: 2.4 s at `chain-2000` against 25 ms with three fixes.

| ID | Task | Where | Evidence | Expected impact | Effort |
| --- | --- | --- | --- | --- | --- |
| L1 | Cache per-cell static analysis by source so save reuses it; skip re-parsing cells already proven valid | `marimo/_ast/codegen.py:642`, `marimo/_ast/toplevel.py:125`, `codegen.py:524` | 81–82% of codegen is `compile_cell` for every cell; a no-change save costs the same as an edit. Same root cause as W4 | Save 308 → 21 ms at 500 cells, 1.9 s → 78 ms at 2,000 (measured, interleaved A/B) | S for an LRU, M to split out `analyze_cell` |
| L2 | Compile lazily in `AppFileManager`; do not load the notebook where only config is needed | `marimo/_ast/cell_manager.py:264`, `marimo/_server/api/endpoints/assets.py:397`, `marimo/_server/host/bridge.py:273`, `marimo/_cli/utils.py:130` | Four call sites each build their own `AppFileManager`; nothing in the server reads compiled cells | Server work at open \~1.5 s → \~0.4 s CPU at 500 cells (estimate from stage timings) | M |
| L3 | Add fast paths to `fixed_dedent` | `marimo/_ast/dedent.py:159`, `:124`; callers `marimo/_ast/parse.py:249`, `:375` | Each cell is tokenized 4 times; at least 70% of `parse_notebook` | `parse_notebook` 2.2–2.3× faster, output-identical on 294,000 fuzz cases (patch saved) | S |
| L4 | Memoize host fingerprints; drop the redundant etag after a bridge save | `marimo/_core/document.py:99`, `marimo/_server/host/bridge.py:375`, `:544` | Recomputed for all cells twice per save and 4 times per open. Same fix as W1 | 84 → 3.3 ms per pass at 500 cells (measured) | S |
| L5 | Bulk graph registration: one ancestor pass, a name index, predecessor-map BFS in `get_path` | `marimo/_runtime/dataflow/graph.py:115`, `edges.py:89`, `topology.py:136`, `__init__.py:116` | Slope 1.8 on star graphs, 2.1 on chains; roughly cubic when definitions follow uses. Overlaps K6 | `chain-2000` 2,674 → 25 ms; `smoke-2000` 298 → 20 ms (measured) | M |
| L6 | Compute `sql_defs` from the cell's own defs | `marimo/_ast/codegen.py:387` | Iterates every notebook variable for every cell | `chain-2000` codegen 451 → 181 ms on its own (patch saved) | S |
| L7 | Make `compile_cell`'s second parse and bytecode lazy; skip tokenizing when the source has no `;` | `marimo/_ast/compiler.py:284`, `:331`, `marimo/_core/code.py:47` | The duplicate parse is 17% and bytecode 16% of compile; `ends_with_semicolon` is 12% on output-heavy notebooks | \~30% off every non-executing compile (estimate); 1.2× on `outputs-500` load from the fast path (measured) | S for the fast path, M for lazy fields |
| L8 | `marimo check`: reuse the graph's compiled cells and IR positions | `marimo/_lint/rules/runtime/reusable_definition_order.py:285`, `marimo/_ast/compiler.py:424` | Compiles every cell twice and parses the notebook twice | 2.47 → \~1.7 s CPU at 500 cells (estimate) | S |
| L9 | Script mode: reuse the parsed body instead of re-deriving each cell from source | `marimo/_ast/compiler.py:607` (`cell_factory`) | Registration is 70% of `python notebook.py` at 2,000 cells; 5–6 tokenize passes per cell | \~20–25% of registration from L3 alone (estimate) | S–M |
| L10 | File-watch reload: reuse analysis for unchanged cells; pair cells by position before all-pairs scoring | `marimo/_session/notebook/file_manager.py:171`, `marimo/_utils/cell_matching.py:323` | A one-cell change reloads everything; a full rewrite scores 250,000 pairs (896 ms at 500 cells) | Single-cell reload becomes parse only; bulk rewrites linear | S–M |
| L11 | Pause the garbage collector during `parse_notebook` | `marimo/_ast/parse.py:1083` | `parse_notebook` 354 → 287 ms with `gc.disable()` at 500 cells | −20–26% on parse, stacking with L3 | S |
| L12 | Index `NotebookDocument` by cell id; register loaded cells in one transaction | `marimo/_messaging/notebook/document.py:113`, `marimo/_ast/cell_manager.py:236` | Linear lookups; 2,001 one-cell transactions 80 → 1.6 ms as one batch | 50–130 ms at 2,000 cells; small at 500 | S–M |
| L13 | Stop the version-strip regex at the first match | `marimo/_utils/generated_with.py:11` | Four full-text regex passes per save: 11 ms at 500 cells | −11 ms per save (patch saved) | S |
| L14 | Startup: lazy URL regex, lazy config read in `assets.py`, defer feature-only imports | `marimo/_utils/url.py:14`, `marimo/_server/api/endpoints/assets.py:62`, `marimo/_runtime/runtime.py:48` | `import marimo` loads 889 modules; one regex is 35 ms and `assets.py` 64 ms at import | \~100 ms off `marimo edit` from the first two; another 100–150 ms estimated | S each |
| L15 | Export: check `is_coroutine` per cell without ancestor walks | `marimo/_convert/script.py:54` | 97% of `export script` on `chain-2000` is this loop | Removes an O(n × depth) walk | S |

## Kernel runtime

The kernel spends 1.4–2.3 ms of CPU around each code cell whose own code takes 14 µs, a 95–180× overhead. Measured in a real `Kernel` with production stream classes; figures are process CPU (min of 3) or deterministic function-call counts, because the machine was loaded.

| Measure | Today | With prototypes |
| --- | --- | --- |
| Run phase, `smoke-500` (251 code cells) | 351 ms | 58 ms |
| Run phase, `smoke-2000` | 2,043 ms | 165 ms |
| Run one cell under lazy startup, `smoke-500` | 310–430 ms | 4–8 ms |
| Run one cell under lazy startup, `smoke-2000` | 2.0–3.6 s | 8–16 ms |
| Run-all, `chain-2000` | 13.0 s | 1.8 s |
| Empty run, `chain-2000` | 525 ms | 1.0 ms |
| Run one leaf cell, `chain-500` | 32 ms | 2.7 ms |
| Kernel messages per executed code cell | 8 | Not prototyped |

Lazy startup is the default (`runtime.auto_instantiate = false`), so the single-cell row is what a user sees when stepping through a large notebook. Most prototypes are in one unapplied diff, [`patches/backend-runtime-proposed.patch`](patches/backend-runtime-proposed.patch), which leaves the notification stream identical.

| ID | Task | Where | Evidence | Expected impact | Effort |
| --- | --- | --- | --- | --- | --- |
| K1 | Reuse the startup compile cache when resolving pending cells | `marimo/_runtime/runtime.py:2088` (`prepare_execution_requests`, compile at `:2139`) | Every run request recompiles all pending cells and rebuilds a throwaway graph: 1.44M calls per single-cell run | \~350 → 4–8 ms at 500 cells; \~2,300 → 8–16 ms at 2,000 (measured) | S |
| K2 | Keep one stdout/stderr pipe and reader thread for the kernel's lifetime | `marimo/_messaging/streams.py:730` (`redirect`), `marimo/_runtime/redirect_streams.py:105` | 2 pipes and 2 threads per cell; 1.5 s of a 1.7 s run phase in a real kernel profile under load | 650 → 29 µs CPU per cell (measured, prototype only) | M |
| K3 | Gate the duckdb hook on `duckdb.imported()` and stop re-parsing the cell | `marimo/_runtime/runner/hooks_post_execution.py:177`, `marimo/_ast/cell.py:259` | `find_spec` plus a third `ast.parse` after every cell; 20% of all function calls | \~85 ms off a 500-cell run, \~340 ms at 2,000 | S |
| K4 | Resolve the executor once per kernel | `marimo/_runtime/runner/cell_runner.py:249`, `marimo/_runtime/executor/evaluator.py:162` | Every run scans every installed distribution's entry points: 6.5 ms, 82% of an empty run | −6.5 ms CPU on every run, slider drag and state update | S |
| K5 | Move the missing-modules check out of `_invalidate_cell_state` | `marimo/_runtime/runtime.py:1262`, `:1274` | An O(n) scan twice per cell whose two results are always equal | −24 ms at 500 cells, −341 ms at 2,000; also restores the alert after a delete | S |
| K6 | Index references by name in the graph; early-exit ancestor checks; fix `get_path` list copies | `marimo/_runtime/dataflow/edges.py:44`, `graph.py:115`, `topology.py:136` | Registration is n^1.8 to n^2.0, and n^2.7 when children register before parents | `chain-2000` registration 2,829 → 13 ms (measured) | S for the index, M for stale/disabled ownership |
| K7 | Compute disabled cells once per run; dispose descendants once; skip unchanged `variables` | `marimo/_runtime/runtime.py:1596`, `:1286`, `:1535` | Per-cell ancestor walks on every run; a 121 KB `variables` message per run at `chain-2000` | `chain-500` empty run 25 → 0.5 ms; single-cell ops 32 → 2.7 ms (measured) | S–M |
| K8 | Scan for changed modules once per run when auto-reload is on | `marimo/_runtime/reload/manager.py:100`, `autoreload.py:349` | Every cell entry walks `sys.modules` and stats each user module; run phase 351 → 1,414 ms | Back to the auto-reload-off level (measured) | S–M |
| K9 | Pass a predicate to `retain_active_states` instead of a set union | `marimo/_runtime/runner/hooks_post_execution.py:268` | Builds the union of all definitions and temporaries per cell | −111 ms at 2,000 cells | S |
| K10 | Coalesce lifecycle notifications; drop the source echo in `planned` | `marimo/_runtime/execution.py:48`, `marimo/_messaging/notification_utils.py:204` | `planned` carries cell source: 523 KB of 1,172 KB at 500 cells | 8 → 3–4 messages per cell; −31% bytes from the echo alone. Same change as W8 and W12 | M–L |
| K11 | Render each markdown cell as soon as it compiles | `marimo/_runtime/runtime.py:2852` | All cells compile before the first output leaves the kernel | First markdown output after \~1 ms instead of \~300 ms | S–M |
| K12 | Paper cuts: skip `_flush_console` when nothing was written; no-op tracer decorators; skip `can_narwhalify` for scalars; sort `used_by` | `hooks_post_execution.py:486`, `marimo/_tracer.py:71`, `marimo/_data/get_datasets.py:40`, `runtime.py:1541` | \~50 µs, 16 context managers and 12–16 µs per variable, each per cell | Small, each | S |
| K13 | Sandbox: update script metadata once per batch | `marimo/_runtime/runtime.py:1128` | Can spawn `uv tree` per importing cell (read from code, not measured) | One subprocess per batch | S |

## Wire protocol and server relay

Traffic is linear in cell count and already compressed; the cost is that the server does notebook-sized work on every edit, save and kernel message. Measured with a Python client that performs the editor's handshake, on the `smoke` fixtures.

| Measure | 100 cells | 500 cells | 2,000 cells |
| --- | --- | --- | --- |
| First load: WebSocket frames | 581 | 2,781 | 11,031 |
| First load: JSON bytes | 316 KB | 1.57 MB | 6.33 MB |
| First load: bytes on the wire (`permessage-deflate`) | 51 KB | 245 KB | 973 KB |
| One-line edit: event-loop CPU | 24 ms | 116 ms | 410 ms |
| One-line edit: bytes pushed back to the editor | 12.5 KB | 44 KB | 168 KB |
| Save after one edit (wall, loaded machine) | 0.2–0.4 s | 0.9–1.5 s | 3.3–3.7 s |
| Page reload: frames replayed | 320 | 1,520 | 6,020 |
| Format all cells (wall) | 12 s | 52–73 s | not run |

A run-all costs 5.5 frames per cell: one `cell` record, three `execution` records (queued, running, completed), one `output`, and a `remove-ui-elements` for each code cell. During it the event loop spends 951 ms of CPU at 500 cells; 33% is decoding and 25% is deep copies.

| ID | Task | Where | Evidence | Expected impact | Effort |
| --- | --- | --- | --- | --- | --- |
| W1 | Cache `code_fingerprint` by source, then make `SessionBridge._mirror` incremental | `marimo/_core/code.py:18`, `marimo/_server/host/bridge.py:606` | Every edit runs `ast.parse` + `ast.dump` + SHA-256 on all cells, on the event loop | Per-edit pass 117 → 4.6 ms at 500 cells with an `lru_cache` (measured) | S, then M |
| W2 | Build the `NotificationMessage` decoder once and decode each kernel message once | `marimo/_messaging/serde.py:22`, callers in `session_view.py:298`, `host/backend.py:520`, `host/session.py:99` | 27 µs per decode against 0.55 µs with a prebuilt `msgspec.json.Decoder`; three decodes per message | Run-all event-loop CPU −28% (measured) | S |
| W3 | Stop deep-copying frozen events in the host stream; serialize once and fan out bytes | `marimo/_core/stream.py:172`, `:320`, `:329` | 4 deep copies per event at 19 µs each; encoding the same event is 0.84 µs | −22% alone; with W2, 930 → 430 ms at 500 cells and 3,974 → 1,972 ms at 2,000 (measured) | M |
| W4 | Save: reuse compiled cells in codegen and compute the etag once | `marimo/_ast/codegen.py:642`, `marimo/_ast/toplevel.py:125`, `host/bridge.py:360` | 86% of save is `compile_cell` for every cell; autosave fires 1 s after each change | Save \~0.9 s → \~0.1 s at 500 cells (estimate) | M |
| W5 | Publish `analysis` and `document` only when they change; keep the analyzer's graph across edits | `marimo/_core/notebook.py:310`, `marimo/_server/host/analysis.py:71` | `analysis` is 85–89% of the bytes pushed per edit; analyzer scales with exponent \~1.95 | Edit push 44 KB → \~3 KB at 500 cells; analyzer 24 → \~1 ms | M |
| W6 | Format with one `ruff` process for all cells | `marimo/_utils/formatter.py:64` | One `python -m ruff` per cell, awaited in sequence; 6.8 s for 101 cells against 0.17 s in one process | Format-all at 500 cells \~60 s → \~1 s | S–M |
| W7 | Coalesce events into batched WebSocket frames; send the initial snapshot as one frame | `marimo/_server/host/session.py:196`, `:248` | 34 µs per frame one by one against 8.7 µs per event when 16 are batched | Frames per run-all 2,781 → 200–700; the larger win is fewer browser tasks | M |
| W8 | Trim the execution lifecycle: skip `output: null`, skip `remove-ui-elements` for cells without UI, send state patches | `marimo/_core/executions.py:585`, `marimo/_server/host/translate.py:152`, `marimo/_runtime/runtime.py:1290` | `execution` records are 50% of bytes; 251 null outputs and 251 no-op removals at 500 cells | Frames per cell 5.5 → 3–3.5 | S for the skips, M–L for patches |
| W9 | Session start: send the document snapshot before the kernel boots; one fingerprint pass, not three | `marimo/_server/session_manager.py:354`, `host/bridge.py:216`, `:502` | Nothing is sent until parse, compile, three fingerprint passes and kernel start all finish | First paint no longer waits \~1–2 s for kernel start | S–M |
| W10 | Replay reconnects as one frame; size the replay log by notebook | `marimo/_core/host.py:276`, `marimo/_core/stream.py:221` | The log holds 1,000 events, fewer than one 500-cell run (2,274), so a mid-run reconnect resets | 1,520 frames → 1; no reset on mid-run reconnect | M |
| W11 | Serve hashed assets with `Cache-Control: immutable` and precompressed bodies | `marimo/_server/api/endpoints/assets.py:113` | 136 eager JS/CSS files, 4.81 MB, no `Cache-Control`, no `content-encoding` | Reload revalidations 136 → 0; remote first load 4.81 → \~1.4 MB | S |
| W12 | Stop echoing source in `planned`; send `CreateNotebookCommand` once per kernel | `marimo/_runtime/execution.py:47`, `host/backend.py:223` | 30% of kernel-to-server bytes are echoed source; each run request pickles 362 KB to the kernel | Run request 362 KB → \~1 KB | S–M |
| W13 | Skip the `variables` broadcast when the map is unchanged | `marimo/_runtime/runtime.py:1537` | 48% of the bytes for a one-cell run at 500 cells, 78% at 2,000 | One-cell run 7.9 → 4.1 KB | S |
| W14 | Drop session-view entries for deleted cells; cap `ui_element_messages` | `marimo/_session/state/session_view.py:405`, `:597` | Read from code, not observed in these fixtures | Memory in long sessions | S |
| W15 | Paper cuts: O(1) insert/move instead of `set_order` with every id; lazy completion docs; one heartbeat timer instead of `wait_for` per event | `host/session.py:198`, `host/notebook_api.py:138` | `set_order` request is 3.7 KB at 500 cells; one completion result is 12.8 KB | Small, each | S |

## Frontend state and rendering

Each kernel event is its own store update, and each update re-reads selectors for every cell, so handling a run-all is quadratic. In real Chromium the WebSocket handler takes 27.4 s for the 500-cell load.

| Cells | WebSocket messages | Time in the message handler (Chromium, no throttle) | Per message |
| --- | --- | --- | --- |
| 25 | 170 | 97 ms | 0.57 ms |
| 50 | 308 | 255 ms | 0.83 ms |
| 100 | 583 | 859 ms | 1.47 ms |
| 250 | 1,408 | 5,850 ms | 4.15 ms |
| 500 | 2,783 | 27,408 ms | 9.85 ms |

The scaling exponent from 100 to 500 cells is 2.15. Only the affected cell is notified and re-rendered; the time goes to recomputing about 10 selectors per mounted cell to learn that 499 of them did not change. The remaining figures in this section are from vitest + jsdom under load, so ratios and counts matter more than milliseconds.

| Measure at 500 cells (jsdom) | Today | With the prototype |
| --- | --- | --- |
| Run-all, store work | 59–344 s, one update per event | 0.20–0.29 s, one update per batch |
| One printed line from a running cell | 18–24 ms | 0.09 ms with nothing subscribed |
| One keystroke, store work | 9.6–47 ms | 0.56 ms with nothing hanging off `notebookAtom` |
| One confirmed edit (three events) | 122 ms | Not prototyped |
| Cells re-rendered by the first keystroke after idle | All of them, twice | 1 |
| `isInVscodeExtension()` document scans per cell mount | 16.4 | 1 for the session |

| ID | Task | Where | Evidence | Expected impact | Effort |
| --- | --- | --- | --- | --- | --- |
| S1 | Batch stream events into one store update per animation frame | `core/notebook/replica/replica.ts:417` (`apply`), `:442` | One `store.set` per event; 77% of a run-all profile is Jotai recomputing invalidated atoms | Run-all store work 59–344 s → 0.2–0.3 s in the bench (measured) | M |
| S2 | Give each cell its own execution, output and freshness slice | `core/executions/atoms.ts:143`, `:172`, `:211`; `core/executions/hooks.ts:29`; `core/cells/cells.ts:573` | Four notebook-wide inputs atoms change identity on every event; `useCellExecution` is created twice per cell | Selector work per event O(n) → O(1); needed after S1 to stay off O(n) per frame | M–L |
| S3 | Compute `isInVscodeExtension()` once | `core/vscode/is-in-vscode.ts:6`, `components/ui/fullscreen.tsx:149`, `:200` | A full-document `querySelector` in render: 16.4 per cell at mount, 8 per status change, \~20,000 for a 500-cell load | One-cell status change 586 → 25 ms at 120 cells in jsdom (measured, patch saved); Chromium cost not yet timed | S |
| S4 | Stop subscribing every cell to document-sync status | `core/saving/document.ts:21`, `core/notebook/document/hooks.tsx:114` | `useSaveNotebook` in every cell reads the status only to get `flush`; each status change re-renders every cell | 4+ full-notebook render waves per typing burst → 0 (measured, patch saved) | S |
| S5 | Make outlines value-stable and resolve headings in one pass | `components/editor/chrome/panels/outline/floating-outline.tsx:15`, `useActiveOutline.tsx:153`, `core/executions/output.ts:86` | One `querySelectorAll` per heading in render, twice per markdown cell run because `timestamp` changes | \~145,000 document scans per run-all of the slow notebook → 0 for unchanged output (estimate) | S–M |
| S6 | Keep `layoutAtom` and the sortable `items` array identity-stable across code edits; stop copying code into `notebookAtom` | `core/cells/layout.ts:144`, `components/editor/renderers/cell-array.tsx:204`, `core/cells/document.ts:63` | A keystroke rebuilds the draft view, change list, follower record and layout; all `SortableCell`s re-render | Keystroke store cost O(n) → O(1) | S for layout, M–L for `notebookAtom` |
| S7 | Remove quadratic helpers in the event path | `core/executions/select.ts:143` (`awaited`), `core/cells/runs.ts:84` (`addExecution`), `core/cells/cells.ts:248` (`addLogs`), `replica/resources/executions.ts:119`, `:207` (`sameShown`) | `addExecution` copies maps per lifecycle change: 43 ms per run-all at 500 cells, 1,057 ms at 2,000; `sameShown` stringifies outputs twice per event | What remains of a run-all after S1 | S each |
| S8 | Make cell actions a per-store singleton; build closed menus lazily; share one `TooltipProvider` | `core/cells/actions.ts:654`, `components/editor/cell/cell-context-menu.tsx:57`, `cell-actions.tsx:66`, `notebook-cell.tsx:628` | `useCellActions()` runs 73.8 times per cell mount and 20–25 times per re-render; each cell renders 5 times while mounting | \~1.2M hook calls removed from a 500-cell mount | S for actions, S–M for menus |
| S9 | Narrow chrome subscriptions that fire on every event | `core/export/hooks.ts:125`, `components/editor/header/status.tsx:81`, `components/editor/cell/collapse.tsx:68`, `core/cells/cells.ts:443` | The save button, status header and collapsed banners read notebook-wide atoms (read from code) | Small, each | S each |
| S10 | Send incremental LSP and Copilot document changes | `core/codemirror/lsp/notebook-lsp.ts:445`, `core/codemirror/copilot/getCodes.ts:12` | Full-document sync: 426 KB per change at 500 cells, 1.7 MB at 2,000 (when enabled) | Payload becomes the edited lines | M |

## Frontend editor and DOM

Every cell mounts a full CodeMirror editor and about 90 hidden chrome elements, so a 500-cell notebook carries roughly 104,000 elements and 72,000 event listeners. Counts and ratios below are from vitest + jsdom on the production modules and the real `<Cell>`; jsdom milliseconds are upper bounds, and style, layout and paint were not measured here.

| Measure at 500 cells | Today | With the prototype fix |
| --- | --- | --- |
| Create every editor (jsdom) | 5.2 s | 2.2 s when the 250 hidden markdown editors are skipped |
| CodeMirror style modules mounted | 1,013 (157 KB) | 15 (12.9 KB) with shared themes |
| Reconfigure every editor (jsdom, with CSS parse) | 12.5 s, then 19.1 s | 0.7 s with shared themes |
| Global listener callbacks per key press | \~4,000 | Not prototyped |
| `document.addEventListener` calls per key press | \~3,000 | Not prototyped |
| Editor dispatches per `variables` message | 1,000 | Not prototyped |
| `fullscreenchange` listeners on `document` | \~5,250 | Not prototyped |

Per cell: 97–149 elements before the editor builds, 10–12 inline SVGs, 13–15 buttons, about 75 store subscriptions, 4 `IntersectionObserver`s and 8 `window` listeners. A hidden markdown editor adds a separate React root with 172 listeners.

| ID | Task | Where | Evidence | Expected impact | Effort |
| --- | --- | --- | --- | --- | --- |
| E1 | Hoist per-editor CodeMirror themes to module constants | `core/codemirror/cells/traceback-decorations.ts:148`, `core/codemirror/go-to-definition/extension.ts:15`, `placeholder/extensions.ts:135` | Each editor adds 2 style modules and rewrites the whole `<style>` tag; 42.5 MB of CSS text assigned during load; nothing is freed | Creation 5.75 → 2.58 s and reconfigure 17–30× faster in jsdom (measured, patch saved) | S |
| E2 | Do not build editors for hidden-code cells; build others on visibility or focus | `components/editor/cell/code/cell-editor.tsx:385`, `core/codemirror/editor-mount-scheduler.ts:58` | The scheduler defers construction but still builds all 500; 268 are never visible | Editor construction −58%; −8,800 elements, −46,000 listeners, −268 React roots | M for hidden cells, L for off-screen cells |
| E3 | Derive a cell's language from its code, not from its editor | `components/editor/notebook-cell.tsx:410` | Hidden markdown cells show a 32 px strip and border, then collapse once the editor exists | Removes 268 layout shifts and 500 cell re-renders on load; prerequisite for E2 | S |
| E4 | Remove per-cell global key listeners: gate `Button`'s `keydown` listener, mount Radix menus on open, share one go-to-definition modifier listener | `components/ui/button.tsx:131`, `components/editor/cell/CreateCellButton.tsx:135`, `cell-context-menu.tsx:201`, `core/codemirror/go-to-definition/underline.ts:66` | 8 callbacks and 6 `addEventListener` calls per cell per key; dispatch grows superlinearly (0.8 ms at 10 cells, 15 ms at 160, jsdom) | Per-key global callbacks 4,000 → single digits | S for `Button` (patch saved), M for menus |
| E5 | Split the editor bundle into per-concern compartments; cache cell-independent extensions | `cell-editor.tsx:202`, `core/codemirror/language/languages/markdown.ts:80` | A theme or settings change rebuilds 72 of 154 extension objects in every editor | A theme toggle becomes one facet change per editor | M |
| E6 | Mount per-cell chrome only for the hovered or focused cell; mount the AI completion editor on demand | `notebook-cell.tsx:627`, `components/editor/ai/ai-completion-editor.tsx:124` | \~90 hidden elements, \~75 subscriptions and one `useChat` client per cell; opening the AI prompt re-renders all 500 `CellEditor`s | \~104,000 → \~60,000 elements; 500 → 1 chat clients (estimate) | M–L |
| E7 | Skip editor dispatches when reactive references and code lenses are unchanged | `core/codemirror/reactive-references/extension.ts:96`, `core/codemirror/code-lens/extension.ts:351` | 2 unconditional dispatches per editor per `variables` message | 1,000 → 0 dispatches for notebooks shaped like the slow one | S |
| E8 | Give `ConsoleOutput`'s layout effect dependencies and memoize it | `components/editor/output/console/ConsoleOutput.tsx:134` | Reads `scrollHeight` after every commit for every named cell (read from code) | Forced layouts in a run-all \~750 → the cells that print | S |
| E9 | Back `useFullScreenElement` with one shared subscription | `components/ui/fullscreen.tsx:60` | One `document` listener per tooltip and popover portal, 10–11 per cell | 5,250 → 1 listener | S |
| E10 | Add `content-visibility: auto` to a cell wrapper; replace the costly selectors | `css/app/Cell.css:10`, `css/common.css:7`, `:29`, `css/globals.css:135` | No containment anywhere; `.hover-actions-parent:has([data-state="open"])` walks each cell subtree; `:root:has(body.dark)` scans from the root (read from CSS) | Style and layout cost proportional to visible cells; needs the browser profile | S for selectors, M for containment |
| E11 | Render the markdown language panel lazily; cache one markdown `LanguageSupport` | `core/codemirror/react-dom/createPanel.tsx:19`, `languages/markdown.ts:101` | A `createRoot` per non-Python editor, re-rendered on every view update | −43,000 listeners and −250 React roots even without E2 | S–M |
| E12 | Defer plugin mounts until near the viewport | `plugins/core/registerReactComponent.tsx:343` | Each plugin output owns a shadow root, a React root and two `MutationObserver`s (read from code) | Matters for output-heavy notebooks, not the slow one | M |

## Task list

The 71 tasks above are ordered here into 17 steps. Steps 1–8 are small changes with a measured effect, steps 9–13 are medium, and steps 14–17 are larger or situational. IDs point to the section tables: B browser, S frontend state, E editor and DOM, W wire and server, L load and save, K kernel.

| Order | Tasks | What it fixes | Effect | Effort | Patch saved |
| --- | --- | --- | --- | --- | --- |
| 1 | E1, B1, B2 | Style recalculation during load | With rows 1 and 2 together: 500-cell load 386 → 49 s (Chromium) | S | Yes |
| 2 | S4, S6 (layout identity), S3 | Whole-notebook re-renders on every keystroke | With rows 1 and 2 together: typing 577 → 76 ms per key (Chromium) | S | Yes |
| 3 | B3 | Arrow-key navigation in command mode | 1.9 s per key at 500 cells today | S | Yes, not validated in a build |
| 4 | E4 (`Button` part), E7, E8, E9 | Per-cell global listeners, no-op editor dispatches, forced layouts | Per-key global callbacks 4,000 → single digits | S | `Button` only |
| 5 | W1 (same as L4), W2 | Server CPU per edit and per kernel message | Edit pass 117 → 4.6 ms; run-all relay −28% | S | Yes |
| 6 | K1, K3, K4, K5, K9 | Kernel overhead per run | Single-cell run under lazy startup \~350 → 4–8 ms | S | Yes, one diff |
| 7 | L1 (same as W4), L3, L6, L13 | Save and parse | Save 308 → 21 ms; parse 2.2× faster | S | Yes, except the L1 cache |
| 8 | W6, W11, W13 | Format-all, asset caching, `variables` rebroadcast | Format-all \~60 s → \~1 s at 500 cells | S | No |
| 9 | S1, then S2 | One store update per kernel event | The largest cost left after rows 1 and 2: 26 s of handler time in a 500-cell load | M, then M–L | Prototype in the bench fixture |
| 10 | E3, then E2 | 501 editors built when 3 are visible | Editor construction −58% from hidden cells alone | S, then M–L | No |
| 11 | W3, W5, W7, W8 with K10 and W12 | Relay deep copies, `analysis` rebroadcast, frame batching, lifecycle messages | Relay CPU −54% with W2; edit push 44 → \~3 KB; frames per cell 5.5 → 3–3.5 | M | No |
| 12 | K2, K6 (overlaps L5), K7 | Per-cell pipes and threads, quadratic graph operations | 650 → 29 µs per cell; `chain-2000` registration 2.8 s → 13 ms | M | K6 and K7 in the kernel diff |
| 13 | L2, L7, W9, K11 | Repeated work when a notebook opens | Server work at open \~1.5 → \~0.4 s CPU at 500 cells | M | `ends_with_semicolon` only |
| 14 | E6, S8, E5, E11 | Per-cell chrome, menus, action hooks, editor reconfigure | \~104,000 → \~60,000 elements; \~1.2M hook calls off a 500-cell mount | M–L | No |
| 15 | E10 | No containment on cells | 500-cell load 386 → 93 s in an injected-CSS experiment; needs a design for clipped hover actions | M | No |
| 16 | B4, B5, B6, S5, S7, S9, S10 | Find, dialogs, scroll, outline, remaining per-event helpers | Find open 8.9 s and palette open 1.9 s today | S–M each | No |
| 17 | W10, W14, W15, K8, K12, K13, L8–L12, L14, L15, E12 | Reconnect replay, auto-reload, CLI commands, startup imports, paper cuts | Small or situational, each | S–M each | L14 URL regex only |

Three investigators wrote overlapping patches for E1, E4, S3 and S4. Use the `frontend-browser-*` versions in [`patches/`](patches/); those were validated in a real build.

## Open questions and things ruled out

Open questions, each blocking or shaping a task:

- [ ] S3: is `data-vscode-theme-kind` set on `<body>` before the first render in the VS Code webview? The patch assumes it is.
- [ ] S1: is it acceptable for queued and running states to appear one frame late once events are batched?
- [ ] B1: carry the `style-mod` change as a `pnpm patch`, or wait for an upstream release?
- [ ] B2: is a static placeholder acceptable, or should one wrapper per visible cell keep a shimmer?
- [ ] E10: `content-visibility` clips the hover actions that sit outside the cell box. Move the chrome inside, or contain an outer wrapper?
- [ ] K2: with one long-lived pipe, late native writes are attributed to the cell current when the bytes are read. Is that acceptable?
- [ ] L5: bulk registration marks a cell disabled even when its disabled ancestor registers after it. Today's per-cell registration misses that case.
- [ ] W7 and W8: batched frames and state patches change the protocol. Do they need a capability flag for older clients?

Limits of these measurements:

- Six benchmarks shared one machine (load average 25–430), so wall-clock values are upper bounds. Counts, CPU time and before/after ratios are the reliable part; a calm rerun of the load and save tables is still owed.
- Chromium headless only. Firefox, Safari and a real GPU compositor were not tested.
- The 500-cell load at 4× CPU and the 1,000-cell load never finished on the production build.
- LSP and Copilot were off in every fixture, so S10 is sized from payload bytes only.

Measured and ruled out:

| Suspect | Result |
| --- | --- |
| WebSocket compression | Already negotiated; wire bytes are 15–18% of JSON |
| Payload sizes | `kernel-ready` is 455 bytes, the save body is `{}`, edits are per-cell deltas |
| Quadratic traffic | None; bytes and frames scale with exponent 1.0 |
| CSS selector matching | 3–4% of style time; the cost is how many elements are restyled |
| Markdown rendering and JSON parsing | Under 0.3% of CPU in every 500-cell profile |
| Memory leak | Heap is flat over three run-all passes (458 → 470 MB) |
| Position in the notebook | Typing costs the same at the top, middle and bottom |
| DOM-only virtualization for typing | Hiding all but 17 cells did not help: 637 against 577 ms per key |
| Dirty tracking and local storage | Two etag comparisons; no notebook-sized writes |
| Kernel notification serialization | 2.3 µs per message |
| Garbage collection in the kernel | 28 ms of a 1,348 ms instantiate |
| Session cache writes, file lock, file write | Under 10 ms per save at 500 cells |

Two bugs found on the way, unrelated to speed: `--profile-dir` breaks server shutdown (`marimo/_session/managers/kernel.py:342`), and notebook lock files in `~/.local/state/marimo/notebook-locks` are never removed.
