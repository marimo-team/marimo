# Frontend (real browser) — large-notebook performance

Real-browser ground truth for the editor at 25–500 cells (1000 attempted). Everything below was measured in
Playwright's Chromium 156 headless shell against `marimo edit` on the working tree at `ce8f85a26`, unless a line says INFERRED.

**Headline.** At 500 cells the editor needs **6 minutes of main-thread work** to finish loading (352–386 s; 72–74% of it
style recalculation), and then spends **0.6–0.9 s of main-thread time per keystroke**. Both are caused by a handful of
specific O(cells) and O(cells²) mechanisms, not by diffuse slowness. Prototyping six small changes (F1–F5) at build time,
with no source edits, cut the 500-cell load to **49 s** (−87%) and typing to **76 ms per keystroke** (−87 to −92%).

## Measurements

### How the numbers were obtained

- Scripts: `.context/perf/frontend-browser/*.ts` (run with `node <script>.ts`, Node 26). Raw JSON: `.context/perf/frontend-browser/out/`.
  Summary tables: `out/load-summary.md`, `out/interact-summary-compact.md`, `out/interact-summary-full.md`, `out/fix-summary.md`.
- Each run starts its own `marimo edit` server on a **fresh copy** of the fixtures (ports 29871–29879) and a fresh browser,
  so every load is a cold kernel start plus run-all (`auto_instantiate = true`). Viewport 1280×720.
- Fixtures: `smoke-N` and `outputs-N` from `.context/perf/fixtures/` (25-cell ones generated with the same generator).
  `smoke-N` has N+1 cells (setup cell).
- CPU slowdown: `Emulation.setCPUThrottlingRate` 1× and 4×.
- Durations named `TaskDuration`, `ScriptDuration`, `RecalcStyleDuration`, `LayoutDuration` are CDP `Performance.getMetrics` deltas (main thread).
- Attribution builds are served by Playwright route interception (`PERF_DIST=<dir>`), so **`marimo/_static/` was never modified**:
  `dist-profile` (`vite.editing-profile.mts`: unminified, source maps, `react-dom/profiling`) and `dist-exp-*`
  (production settings plus prototype fixes applied by a build-time `load` hook, `vite.perf-experiment.mts`).
- The page probe (`lib.ts`: wrapped `addEventListener`, observers, `WebSocket`, a per-frame sampler) costs about 1.3% of
  load CPU at 500 cells (`tick` + `querySelectorAll` in the load profile) and was switched off after load for interactions.
- **Noise.** The machine was heavily oversubscribed by the other investigators (load average 75–430 on 14 cores).
  Durations are inflated and noisy; counts (style recalcs, React commits, renders, listeners, DOM nodes) are exact.
  Before/after pairs were run back to back in the same window. Treat single absolute latencies as ±50%.

### M1. Cold load, `smoke`, 1× CPU (median of 3 runs; 2 runs at 500)

`node load.ts smoke <N> 1 3 base` → `node summarize-load.ts base`

| Metric | 25 | 50 | 100 | 250 | 500 | exponent (100→500) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| first cell painted = all cells in DOM (ms) | 3,314 | 4,256 | 4,804 | 5,104 | 6,563 | 0.19 |
| run-all complete, all cells idle (ms) | 3,898 | 5,506 | 6,820 | 17,087 | 64,561 | 1.38 |
| all editors mounted (ms) | 4,698 | 8,339 | 17,420 | 86,784 | 356,599 | 1.87 |
| main thread quiet (ms) | 3,898 | 5,586 | 17,262 | 86,776 | 357,855 | 1.88 |
| long tasks (count) | 3 | 8 | 136 | 395 | 1,067 | 1.27 |
| total blocking time (ms) | 230 | 461 | 2,740 | 49,594 | 250,894 | **2.83** |
| longest task (ms) | 168 | 275 | 499 | 1,154 | 2,350 | 0.96 |
| TaskDuration (ms) | 1,920 | 4,625 | 13,367 | 83,596 | 352,423 | **2.03** |
| ScriptDuration (ms) | 806 | 1,308 | 2,711 | 13,223 | 58,029 | 1.89 |
| RecalcStyleDuration (ms) | 824 | 2,824 | 9,545 | 63,186 | 259,896 | **2.05** |
| RecalcStyleCount | 372 | 483 | 742 | 1,269 | 2,510 | 0.75 |
| LayoutDuration (ms) / LayoutCount | 44 / 78 | 68 / 98 | 111 / 227 | 620 / 399 | 2,430 / 790 | 1.91 / 0.77 |
| WebSocket messages / KB | 170 / 87 | 308 / 163 | 583 / 308 | 1,408 / 767 | 2,783 / 1,531 | 0.97 |
| time inside the WS message handler (ms) | 97 | 255 | 859 | 5,850 | 27,309 | **2.15** |
| frame gaps > 100 ms | 3 | 7 | 58 | 311 | 762 | 1.61 |

The cells appear after 3–7 s at every size (server and kernel start included). Everything after that is quadratic: style recalculation, script, and
WebSocket handling all have exponent ≈ 2. A same-window repeat at 500 gave TaskDuration 385.9 s, style 276.6 s.

`outputs` (1×) is the same curve, 5–10% higher: TaskDuration 2.1 / 4.9 / 14.6 / 90.9 / **371.9 s**; style 0.9 / 3.0 / 10.4 / 68.2 / 271.0 s;
all editors mounted at 4.9 / 8.6 / 18.1 / 94.5 / 378.1 s.

**4× CPU** (`node load.ts <shape> <N> 4 …`):

| | smoke 25 | smoke 100 | smoke 250 | smoke 500 |
| --- | ---: | ---: | ---: | ---: |
| run-all complete (s) | 7.5 | 23.9 | 119.9–130.5 | **not complete after 600 s** (timeout) |
| all editors mounted (s) | 12.6 | 78.9 | **569.3** (1 run) | not measured |
| TaskDuration (s) | 9.6 | 75.8 | 559.3 | – |
| RecalcStyleDuration (s) | 4.1 | 51.0 | 358.4 | – |
| total blocking time (s) | 4.3 | 51.8 | 463.5 | – |

At 4× a 250-cell notebook keeps the main thread busy for 9.5 minutes. The kernel's messages starve the editor queue:
during the 170 s run phase only 4 editors mounted (`timeline.ts`).
(The first 4×/250 runs ended early at 8–9 editors because "quiet" was detected between short tasks; `load.ts` now also
requires every editor, and the 250 column is from the corrected run.)

**1000 cells:** run-all had not completed after 600 s at 1×; a second attempt was stopped after 52 minutes, still loading.

### M2. Page inventory after load (`smoke`, 1×)

| Metric | 25 | 100 | 250 | 500 | per cell |
| --- | ---: | ---: | ---: | ---: | ---: |
| DOM elements / nodes (CDP) | 5,201 / 7,939 | 18,758 / 29,090 | 45,971 / 71,740 | 91,027 / 142,126 | 182 / 284 |
| DOM max depth | 30 | 30 | 30 | 30 | constant |
| JS event listeners (CDP) | 4,849 | 17,430 | 42,927 | 85,294 | 170 |
| `addEventListener` / `removeEventListener` calls | 4,495 / 208 | 16,083 / 771 | 39,409 / 1,898 | 78,262 / 3,772 | 156 / 7.5 |
| `.cm-editor` (EditorView) | 26 | 101 | 251 | 501 | 1 |
| … in hidden-code markdown cells (`h-0 overflow-hidden`) | 13 | 50 | 125 | 250 | 50% |
| … visible code but offscreen | 11 | 49 | 124 | 249 | 49.7% |
| … in the viewport | 2–3 | 2–3 | 2–3 | **3** | – |
| `.cm-line` | 312 | 1,193 | 2,988 | 5,883 | 12 |
| `<style>` elements / CSS rules | 3 / 4,641 | 3 / 5,166 | 3 / 6,216 | 3 / **7,966** | +7 rules |
| ResizeObserver created / `observe` | 83 / 53 | 307 / 202 | 757 / 502 | 1,507 / 1,002 | 3 / 2 |
| IntersectionObserver created / `observe` | 104 / 61 | 404 / 242 | 1,005 / 660 | 2,007 / 1,600 | 4 / 3 |
| MutationObserver created / `observe` | 30 / 170 | 105 / 619 | 255 / 1,526 | 505 / 3,039 | 1 / 6 |
| `setTimeout` calls | 185 | 668 | 1,756 | 3,566 | 7 |
| JS heap after GC (MB) | 51 | 115 | 245 | **458** | 0.86 |

`outputs-500`: 105,458 elements, 112,451 listeners, 518 MB heap.

`addEventListener` calls per cell by target and type (500 vs 25 cells; full list in `out/load-summary.md`):

| target\|type | calls at 500 (add/remove) | per cell |
| --- | ---: | ---: |
| document\|fullscreenchange | 6,043 / 1,004 | 12 |
| document\|keydown | 4,044 / 251 | 8 |
| div\|scroll + div.flex\|scroll + div.relative\|scroll + body\|scroll | 6,507 / 0 | 13 |
| window\|resize, input\|invalid, .cm-scroller\|scroll | 1,002–1,006 each | 2 each |
| editor content DOM: 26 event types (click, mousedown, paste, drag*, touch*, composition*, wheel, …) | 503 each | 1 each |
| window\|keydown, keyup, blur, mouseleave, scroll; document\|selectionchange; MediaQueryList\|change | 501–502 each | 1 each |

Every one of these scales linearly with the cell count.

WebSocket traffic during load (`smoke`, n / handler ms / KB):

| event | 25 | 100 | 250 | 500 |
| --- | ---: | ---: | ---: | ---: |
| `execution` | 78 / 57 / 40 | 303 / 611 / 154 | 753 / 4,373 / 384 | 1,503 / **20,603** / 767 |
| `output` | 26 / 20 / 9 | 101 / 203 / 35 | 251 / 1,368 / 90 | 501 / **6,430** / 178 |
| `cell` | 26 / 4 / 27 | 101 / 8 / 98 | 251 / 26 / 253 | 501 / 53 / 515 |
| `remove-ui-elements` | 13 / 0 / 1 | 51 / 0 / 4 | 126 / 1 / 10 | 251 / 1 / 20 |

Three `execution` events per cell; the handler costs 0.7 ms per event at 25 cells and **13.7 ms per event at 500**.

### M3. Interaction latency (`smoke`, production build)

`node interact.ts smoke <N> 1,4 base --panels` → `node summarize-interact.ts base smoke <rate> --compact`.
Latency = trigger event timestamp → the frame after the UI condition holds (typing: median keydown → post-paint task).
Task = main-thread `TaskDuration` for the interaction (typing: **per keystroke**, 80 ms cadence).

**1× CPU**

| Interaction | 25: latency / task ms | 100 | 250 | 500 | exponent (latency / task) |
| --- | ---: | ---: | ---: | ---: | ---: |
| type, cell near top | 19 / 41 | 21 / 111 | 42 / 358 | 107 / **695** | 0.55 / 0.97 |
| type, middle | 15 / 42 | 24 / 119 | 42 / 364 | 217 / **917** | 0.81 / 1.03 |
| type, bottom | 14 / 41 | 22 / 105 | 48 / 379 | 110 / **614** | 0.67 / 0.94 |
| Enter (newline), middle | 28 / 72 | 94 / 255 | 75 / 488 | 260 / 1,337 | 0.65 / 0.94 |
| 2.5 s after typing stops (task only) | 75 | 209 | 351 | 1,920 | 0.99 |
| create cell (Mod-Shift-P) | 99 / 230 | 409 / 1,950 | 762 / 1,591 | **5,386** / 7,228 | 1.23 / 1.03 |
| hide code (Mod-H) | 37 / 144 | 190 / 435 | 286 / 996 | 1,332 / 8,083 | 1.11 / 1.24 |
| move cell down | 44 / 92 | 149 / 533 | 281 / 1,000 | 9,877 / 14,629 | 1.59 / 1.54 |
| move cell up | 42 / 123 | 206 / 567 | 300 / 818 | 1,862 / 3,831 | 1.16 / 1.06 |
| delete cell (Shift-Backspace) | 36 / 146 | 486 / 1,188 | 324 / 1,148 | 14,342 / 20,255 | 1.71 / 1.44 |
| run one cell (Mod-Enter) → idle | 80 / 75 | 856 / 922 | 487 / 490 | 3,224 / 3,141 | 1.07 / 1.08 |
| run all → idle | 944 / 524 | 6,359 / 4,813 | 15,848 / 16,165 | **57,444** / 57,698 | 1.33 / 1.54 |
| focus another cell (click) | 33 / 27 | 76 / 361 | 73 / 103 | – | 0.37 / 0.69 |
| focus next cell (Mod-Shift-J) | 21 / 18 | 40 / 43 | 32 / 50 | 205 / 346 | 0.62 / 0.85 |
| command mode, arrow key (per key) | 31 / 43 | 154 / 272 | 229 / 268 | **1,875** / 2,136 | 1.25 / 1.15 |
| command palette open (Mod-K) | 112 / 156 | 405 / 568 | 785 / 851 | 1,892 / 2,109 | 0.92 / 0.83 |
| command palette typing (per key) | 12 / 6 | 8 / 19 | 10 / 57 | 14 / 240 | 0.04 / 1.19 |
| find in notebook: open (Mod-F) | 20 / 27 | 225 / 276 | 100 / 145 | **8,944** / 10,851 | 1.67 / 1.66 |
| find: typing the query (per key) | 16 / 29 | 38 / 185 | 118 / 305 | 201 / 1,103 | 0.87 / 1.15 |
| scroll top→bottom, 6 s of wheel events (task only) | 416 | 2,177 | 3,542 | 6,195 | 0.89 |
| window resize 1280→1000 | 62 / 83 | 608 / 708 | 526 / 667 | 852 / 2,791 | 0.83 / 1.07 |
| save (Mod-S) → response | 189 / 60 | 1,287 / 410 | 3,672 / 1,772 | 1,412 / 2,163 | 0.79 / 1.26 |
| open variables panel | 51 / 98 | 151 / 438 | 370 / 1,204 | 354 / 2,558 | 0.70 / 1.09 |
| open outline panel | 20 / 32 | 33 / 76 | 475 / 1,129 | 72 / 4,422 | 0.71 / 1.70 |
| open documentation panel | 30 / 37 | 84 / 614 | 40 / 82 | 77 / 249 | 0.23 / 0.44 |
| open dependencies panel | 34 / 38 | 36 / 507 | 45 / 136 | 115 / 461 | 0.35 / 0.67 |

Scroll at 500 cells: 10 fps over the 6 s wheel run, 9 long tasks totalling 4.8 s, longest frame gap 1.3 s (25–250 cells: 58–60 fps).

**4× CPU**

| Interaction (latency / task ms) | 25 | 100 | 250 | 500 |
| --- | ---: | ---: | ---: | ---: |
| type, middle (per key) | 50 / 221 | 267 / 621 | 609 / 1,022 | editor could not be focused within 30 s |
| create cell | 603 / 1,212 | 2,529 / 4,201 | 6,376 / 10,760 | – |
| hide code | 181 / 550 | 1,528 / 4,802 | 2,788 / 9,724 | – |
| run one cell | 307 / 383 | 4,936 / 2,825 | 3,523 / 4,100 | 26,973 / 39,337 |
| command mode, arrow key | 151 / 179 | 919 / 1,072 | 2,500 / 2,531 | 11,736 / 10,599 |
| find: open | 204 / 240 | 1,331 / 1,504 | 2,390 / 2,694 | 13,910 / 24,234 |
| window resize | 280 / 356 | 1,643 / 1,883 | 3,222 / 3,622 | 5,096 / 14,332 |
| run all (latency) | 2,051 | 23,956 | 119,065 | 321,233 |

Even at **25 cells** every keystroke at 4× is a long task (20 long tasks for 20 keys, 215 ms of work per key).

**Which interactions scale with the notebook although they touch one cell?** All of them. Typing, Enter, create, delete,
move, hide, run-one, command-mode arrows, find, resize and save have task exponents of 0.9–1.5. The weakest are focusing
the next cell (task exponent 0.85), palette typing (latency flat, work grows) and the documentation and dependencies panels.

### M4. CPU attribution at 500 cells (profiling build, `Profiler` domain)

`PERF_DIST=dist-profile node trace.ts smoke 500 load,type,addcell,runall prof500 --react --why --interval=1000` →
`node analyze-profile.ts out/attr/prof500-smoke-500-<scenario>.cpuprofile dist-profile` (saved as `*.profile.txt`).
Percentages are of active (non-idle) samples. The profiling build adds ~10% recorder overhead (`logComponentRender`, `visit`).

| Group (self time) | (a) load, 417.6 s | (b) typing 30 keys, 105.9 s | (c) add 3 cells, 39.0 s | (d) run all, 97.6 s |
| --- | ---: | ---: | ---: | ---: |
| CodeMirror (`EditorView` constructor: forced style recalc) | **49.2%** | 1.0% | 0.9% | – |
| `(program)`: style, layout, paint outside script | **33.5%** | 10.5% | 17.2% | 17.1% |
| React render/commit/scheduler | 4.6% | **29.1%** | **29.3%** | 9.3% |
| `querySelector` (`isInVscodeExtension`) | 1.0% | **28.2%** | **20.9%** | 11.0% |
| jotai | 4.9% | 7.0% | 5.7% | **35.6%** |
| GC | 1.7% | 6.5% | 5.5% | 6.1% |
| app `src/components/editor` | 1.1% | 3.4% | 4.3% | 2.9% |
| radix / react-aria / dnd-kit / floating-ui | 0.6% | 3.1% | 2.7% | 0.9% |
| markdown / HTML parsing | < 0.3% | < 0.3% | < 0.3% | < 0.3% |

Top functions:

| Scenario | Function (source) | Time | Share |
| --- | --- | ---: | ---: |
| load | `EditorView` constructor, self (`@codemirror/view/dist/index.js:7910`), called from `processNext` (`frontend/src/core/codemirror/editor-mount-scheduler.ts:58`) → `cell-editor.tsx:396` → `:329` | 188.9 s | 45.2% |
| load | `(program)` | 140.1 s | 33.5% |
| load | `getScrollOffset` (`@codemirror/view/dist/index.js:6678`), self | 7.9 s | 1.9% |
| load | WS `message` → `apply` (`frontend/src/core/notebook/replica/replica.ts:417`) → `setStream` (`:266`) → jotai `recomputeInvalidatedAtoms` (250-cell profile: 5.0 s inclusive, 5.9%) | – | ~5% |
| load | `ConsoleOutput` layout effect (`frontend/src/components/editor/output/console/ConsoleOutput.tsx:134`), self | 3.8 s | 0.9% |
| typing | `isInVscodeExtension` (`frontend/src/core/vscode/is-in-vscode.ts:6`) from `Comp` (`frontend/src/components/ui/fullscreen.tsx:145`), inclusive | **29.8 s** | 28.1% |
| typing | React `renderRootSync`, inclusive | 64.5 s | 60.9% |
| typing | `useCellActions` (`frontend/src/core/cells/actions.ts:655`), inclusive | 7.6 s | 7.2% |
| typing | `EditableCellComponent` (`frontend/src/components/editor/notebook-cell.tsx:371`), inclusive | 6.9 s | 6.5% |
| typing | `flushPassiveEffects`, inclusive | 9.1 s | 8.6% |
| add cell | `isInVscodeExtension`, inclusive | 8.1 s | 20.8% |
| add cell | `useCellActions`, inclusive | 2.6 s | 6.7% |
| run all | WS `message` (`frontend/src/core/transports/server.ts:112`) → `apply` → jotai `storeSet`, inclusive | **45.5 s** | 46.5% |
| run all | jotai `recomputeInvalidatedAtoms`, inclusive | 39.0 s | 39.9% |
| run all | `isInVscodeExtension`, inclusive | 10.6 s | 10.8% |
| run all | `cellExecutionView` (`frontend/src/core/executions/select.ts:166`), inclusive | 4.9 s | 5.1% |
| run all | `Time.parse` (`frontend/src/utils/time.ts:35`), inclusive | 2.7 s | 2.7% |

### M5. React commits at 500 cells (commit recorder on the profiling build)

Extended in scratch with an aggregator and a "why did it render" recorder (`why-recorder.ts`: diffs props, hook
state and contexts, and prints the jotai atom's `read` source for a changed `useAtomValue`).

| Scenario (500 cells) | commits | component renders | React render time | cells touched per commit (p95) |
| --- | ---: | ---: | ---: | ---: |
| load | 1,444 | 434,627 | 11.5 s | 3 (max 501) |
| type 30 characters | 206 | **1,432,568** | 62.4 s | **501** |
| add 3 cells | 47 | 341,343 | 19.7 s | 504 |
| run all | 605 | 328,369 | 20.2 s | 3 (max 504) |

**Per keystroke at 500 cells: 6.9 commits and 47,750 component renders.** Each keystroke renders
`EditableCellComponent` 768 times (501 cells × 1.5), `SortableCell` 1,517 times (× 3), `CellEditorInternal` 769,
`ConsoleOutput` 770, `Button` 3,076, `Tooltip` 2,315, `Comp` (portal wrapper) 772.

Why they render (250 cells, counts for 30 keystrokes; identical pattern at 25 and 500):

| Count | Component | Cause reported by the recorder |
| ---: | --- | --- |
| 10,988 | `EditableCellComponent` | hook #165: `useAtomValue` of `atom((get) => { const running = get(runningAtom); return running ? get(running.sync.statusAtom) : …` — the **document sync status** |
| 11,032 | `CellEditorInternal` | hook #47: the same sync status atom |
| 11,210 + 11,040 | `SortableCell` | dnd-kit sortable context (`items` changed) |
| 89 each | `CellArray`, `CellArrayInternal`, `CellColumn` | `useAtomValue(layoutAtom)` — 3 times per keystroke |
| 44 each | `SetupCellComponent`, `FilenameForm`, `DocumentSyncStatus`, `SaveComponent` | sync status atom |

The same two causes re-render every cell in the other one-cell interactions at 250 cells: add 3 cells 43 commits / 142,344
renders; delete 3 cells 440 / 193,054; move ×4 38 / 186,383; hide/show ×4 39 / 213,557; run one cell ×3 471 / 114,445;
focus next/previous ×6 23 / 60,745. Command-mode arrow keys ×6: 23 commits / 90,819 renders, caused by a different atom (F9).

### M6. Style and layout

CDP deltas at 500 cells (production build, 1×):

| Phase | RecalcStyle ms / count | Layout ms / count | Script ms | Notes |
| --- | ---: | ---: | ---: | --- |
| load | 259,896 / 2,510 | 2,430 / 790 | 58,029 | 104 ms per recalc; 5.0 recalcs per editor mount |
| typing, per keystroke | 0.8–3.5 / 3–9 | 3.8–10.6 / 2.2 | 514–835 | style and layout are not the typing problem |
| add cell | 418 / 41 | 53 / 9 | 6,002 | one document-wide recalc per new editor |
| run all | 2,810 / 993 (profiling build) | 227 / 17 | 79,759 | |
| scroll, 6 s | 129 / 94 | 85 / 36 | 4,835 | |
| find: open | 22 / 12 | **8,359** / 2 | 2,270 | one 8.3 s forced layout |
| command palette open | **1,428** / 18 | 61 / 5 | 283 | document-wide recalc when the dialog opens |
| window resize | 483–501 / 9–13 | 217–245 / 2 | 1,890–2,092 | |

Trace of a 4 s window in the middle of a 250-cell load (`node trace.ts smoke 250 midload tr --trace --invalidation`,
`devtools.timeline` + invalidation tracking, which inflates durations):

- 56 style recalcs, 5.94 s of an 8.6 s main-thread span. 38 of them touched > 1,000 elements (median 3,793, max 7,706).
- **45 of 56 were forced inside script (4.17 s)**. First stack frame: `EditorView` constructor at
  `@codemirror/view/dist/index.js:7964` (the `document.fonts.ready` read, four lines after `this.mountStyles()` at `:7960`):
  14 calls, 3.73 s, i.e. **266 ms of forced style recalc per editor**. Then `getScrollOffset` (11),
  `isScrolledToBottom` (6), radix `getAnimationName` (8), `ConsoleOutput.tsx:144` (7).
- Invalidation reasons: `@keyframes rule change` 82,888 elements, `Animation` 64,114, `Style rule change` 41,354,
  `Affected by :has()` 229.
- The 3,793 elements per recalc equal the number of animated skeleton bars still on the page (≈ 237 unmounted cells × 16 bars).
- Layout: 24 layouts, 54 ms; 21 forced, 14 of them from the `EditorView` constructor.

Selector statistics (`--selector-stats`, 100 cells; overhead is ~10× on large recalcs, ranking is valid):

| Scenario | recalc total | selector matching | `:has()` | universal `*` | `:where/:is/:not` | CodeMirror `.ͼ`/`.cm-` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mid-load window | 11,777 ms | **401 ms (3.4%)** | 8.3% of matching | 33.4% | 60.4% | 20.5% |
| add 3 cells | 7,152 ms | 286 ms (4.0%) | 12.3% | 30.4% | 54.1% | 27.7% |
| scroll 5 s | 3,880 ms | 166 ms (4.3%) | 14.2% | 30.4% | 54.3% | 16.3% |
| typing 30 keys | 49 ms | 2.8 ms | 60.7% | 9.8% | 16.6% | 69.1% |

Most expensive selectors: `.ͼ4 .cm-content :focus ::selection` (28 ms, 284,723 attempts, 0 matches),
`.marimo-cell:has(.mo-ai-deleted-cell) .cm-content` (14–18 ms for 330 attempts),
`:root:has(body.dark)` (9–17 ms for 18–28 attempts), `.ͼ6w .cm-content ::selection`,
Tailwind `:where(.space-y-* > :not(:last-child))` and `:where(.marimo-cell… > :not(:last-child))` (3–8 ms each, 71k–142k attempts).
**Selector matching is 3–4% of style time.** The cost is the number of elements restyled, not the selectors.

### M7. Experiments (before/after, same window)

**CSS injected with an init script, production build** (`node load.ts smoke <N> 1 1 <tag> --css=css/<file>`):

| Injected CSS | 250: TaskDuration / style / TBT (s), 2 rounds | 500: TaskDuration / style / TBT (s) |
| --- | ---: | ---: |
| none (250: `x0-noop`; 500: the `static-prod` run below) | 88.1, 86.9 / 65.3, 64.8 / 53.1, 52.5 | 385.9 / 276.6 / 279.9 |
| `.mo-code-placeholder-bar { animation: none !important }` | 35.5, 36.0 / 22.1, 21.5 / 9.7, 9.9 | 164.0 / 92.7 / 78.5 |
| `.marimo-cell { content-visibility: auto; contain-intrinsic-size: auto 240px }` | 18.5, 23.6 / 5.3, 6.1 / 3.0, 4.1 | 93.1 / 21.0 / 26.2 |
| both | 14.7, 18.2 / 3.2, 4.8 / 2.2, 3.1 | 68.0 / 15.9 / 9.5 |

`content-visibility` on the cell clips the hover actions that sit outside the cell box, so it is a sizing experiment, not a drop-in fix.

`content-visibility` and hiding all but 17 cells with `display: none` (`interact.ts --virtualize`) do **not** help typing or
adding a cell at 500 cells: typing 577 ms per key (base) vs 346–614 ms (content-visibility) vs 637 ms (`display: none`);
create cell 3,962 ms vs 4,527 ms vs 1,498 ms. Typing is script, not style.

**Prototype fixes applied at build time** (`vite.perf-experiment.mts`; `PERF_DIST=dist-exp-<name> node load.ts …`):

| Build | Fixes | 250 load: TaskDuration / style (s), 2 rounds | editors mounted after cells (s) |
| --- | --- | ---: | ---: |
| `static-prod` | none (copy of `_static`, served the same way) | 95.2, 96.1 / 71.0, 69.7 | 93.6, 94.0 |
| `themes` | F1 shared CodeMirror themes only | 91.1, 96.3 / 67.9, 71.2 | 89.8, 94.5 |
| `load` | F1 shared themes + style-mod skips unchanged sheet | 28.3, 20.3 / **4.0, 4.5** | 10.2, 19.3 |
| `all` | F1 themes, F2 no pulse, F3, F4, F5 (no style-mod change) | 35.3, 37.9 / 22.0, 22.7 | 34.3, 36.5 |
| `all2` | `all` + style-mod change | **13.0, 12.0** / **1.4, 1.4** | 12.1, 11.2 |

| 500 cells, 1× | `static-prod` | `all2` | change |
| --- | ---: | ---: | ---: |
| load: all editors mounted (s) | 393.3 | **54.8** | −86% |
| load: TaskDuration (s) | 385.9 | **48.9** | −87% |
| load: RecalcStyleDuration (s) | 276.6 | **4.3** | −98% |
| load: ScriptDuration (s) | 69.0 | 38.4 (26.2 s of it in the WS handler) | −44% |
| load: long tasks / total blocking time | 1,149 / 279.9 s | 28 / 5.0 s | −98% |
| type, middle: task per key (ms) | 577 | **76** | −87% |
| type, middle: key→paint p50 / p95 (ms) | 85 / 1,659 | **34 / 57** | |
| type, top / bottom: task per key (ms) | 807 / 900 | 76 / 76 | −91% |
| Enter, middle: task per key (ms) | 1,407 | 126 | −91% |
| create cell: latency (ms) | 3,962 | 658 | −83% |
| hide code: latency (ms) | 1,699 | 526 | −69% |
| move cell down: task (ms) | 6,382 | 642 | −90% |
| run one cell: latency (ms) | 1,403 | 898 | −36% |
| command mode arrow key: latency (ms) | 766 | 416 | −46% (F9 not included) |
| delete cell: latency (ms) | 1,424 | 1,337 | none |

4× CPU with the same `all2` build: 250 cells TaskDuration 559.3 s → **51.0 s**, all editors mounted 569.3 s → 51.1 s,
total blocking time 463.5 s → 8.2 s. 500 cells: 198.3 s of main-thread work, editors mounted at 198.7 s, of which
**102.6 s is the WebSocket handler** (F6) and 16.6 s style; the unpatched build had not finished run-all after 600 s.

Typing at 250 cells, isolating each fix (`node summarize-fix.ts 250 …`; middle cell, task ms per key / key→paint p95):
base 323 / 328 → F3 only 88 / 65 → F3+F4 53 / 36 → F3+F4+F5 50 / 29 → all 42 / 28.

### M8. Memory (`node memory.ts smoke <N> 3`, heap after 3 forced GCs)

| | 25 | 100 | 250 | 500 |
| --- | ---: | ---: | ---: | ---: |
| heap after load (MB) | 51.1 | 114.7 | 242.2 | 458.4 |
| after run-all 1 / 2 / 3 (MB) | 52.9 / 53.5 / 54.1 | 119.1 / 119.8 / 120.6 | 251.3 / 251.7 / 252.3 | 468.0 / 469.2 / 470.2 |
| DOM nodes, load → after 3 run-all passes | 7,939 → 7,995 | 29,073 → 29,075 | 71,736 → 71,562 | 142,126 → 141,679 |
| listeners, load → after 3 run-all passes | 4,849 → 5,030 | 17,442 → 17,964 | 42,819 → 43,900 | 85,294 → 87,361 |

No leak: +2–4% on the first run-all, then +0.2–0.6 MB per run-all. Node counts are flat, so no detached-DOM growth.

Live-object sampling after a 100-cell load (`PERF_DIST=dist-profile node heap.ts smoke 100`, 108.9 MB, 1.08 MB per cell):
react-dom 35.0 MB (fibers and hooks), jotai 17.2 MB (**`useSetAtom` 13.6 MB**), react 5.7 MB, `src/components/editor` 4.9 MB,
`@codemirror/view` + `state` 6.4 MB, radix 6.8 MB, zod 2.4 MB. By caller: **`useCellActions` retains 18.0 MB (17% of the heap, 180 KB per cell)**.

## Findings (highest impact first)

### F1. Every editor mount rewrites CodeMirror's style sheet and restyles most of the document

- **Category:** `caching`, `algorithms`, `batching`
- **Where:**
  - `node_modules/style-mod/src/style-mod.js:135` (`StyleSet.mount`): `this.styleTag.textContent = text` runs on every
    `EditorView` construction (`mountStyles`), even when no module was added.
  - Per-cell themes, each adding its rules again for every editor:
    `frontend/src/core/codemirror/go-to-definition/extension.ts:15` (`goToDefinitionBundle`, `EditorView.baseTheme`),
    `frontend/src/core/codemirror/placeholder/extensions.ts:135` (`EditorView.theme`),
    `frontend/src/core/codemirror/cells/traceback-decorations.ts:148` (`errorLineHighlighter`, `EditorView.theme`).
    The same pattern is in `cells/debugger-decorations.ts:83` and `:180` and `cells/line-timing-decorations.ts:153` (not active in these runs).
  - Mounting is driven by `frontend/src/core/codemirror/editor-mount-scheduler.ts:58` (`processNext`) and
    `frontend/src/components/editor/cell/code/cell-editor.tsx:396`.
- **Evidence:** MEASURED. CodeMirror's `<style>` has 535 rules at 50 cells; 7 rule texts repeat once per cell
  (`cmstyles.ts`: `.ͼX .underline`, `.ͼX .cm-placeholder`, 3× `.cm-clickable-placeholder`, 2× `.cm-error-line`); total rules grow
  4,641 → 7,966 from 25 to 500 cells. Each mount forces a style recalc inside the `EditorView` constructor: 266 ms per editor
  at 250 cells in the trace, 188.9 s of self time at 500 cells (45% of load CPU). Sharing the themes alone changes nothing
  (91–96 s vs 95–96 s at 250). Sharing the themes **and** skipping the unchanged write: style 70.4 s → 4.3 s, TaskDuration 95.6 s → 24.3 s.
- **Why it is slow:** style-mod replaces the whole sheet text on each mount. The sheet contains `@keyframes cm-blink`, so
  Chrome treats every rewrite as a keyframes and rule change and restyles thousands of elements (F2 makes that set large).
  The constructor then reads `document.fonts.ready` (`:7964`), which makes Chrome update style and layout synchronously
  (the stack frame is MEASURED; that this getter is the trigger is INFERRED). Cost per mount grows with the document, so load is O(cells²).
- **Proposed fix:** (1) hoist the three themes to module constants (`patches/frontend-browser-codemirror-shared-themes.patch`).
  (2) Make style-mod skip the write when the text is unchanged (`patches/frontend-browser-style-mod-skip-unchanged-sheet.patch`;
  apply with `pnpm patch` and send upstream). Alternative to (2): mount all editors' style modules once, before the first
  editor, and give editors a shared root. Add a lint or test that fails when an extension factory calls `EditorView.theme` per cell.
- **Expected impact:** 250-cell load 95.6 s → 24.3 s of main-thread time with this alone; with F2, 12.5 s. Adding a cell
  no longer restyles the document (create cell at 500: RecalcStyle 368 ms → 34 ms).
- **Effort / risk:** S. Theme hoisting is mechanical. The style-mod patch must keep ordering semantics; it only skips identical text.

### F2. Code placeholders run ~16 infinite animations per unmounted cell

- **Category:** `lazy-init`, `algorithms`
- **Where:** `frontend/src/components/editor/cell/code/code-placeholder.tsx:37` (`CodePlaceholder`, one `<Skeleton>` per
  code line, up to 50) and `frontend/src/components/ui/skeleton.tsx:10` (`animate-pulse`).
- **Evidence:** MEASURED. 1,490 elements with a running `pulse` animation at 100 cells with 9 editors mounted (`explore6.ts`);
  ≈ 8,000 at the start of a 500-cell load. In the trace, each recalc touches 3,793 elements = the bars still on the page;
  reasons `@keyframes rule change` (82,888) and `Animation` (64,114). Disabling the animation with one injected CSS rule:
  250 cells 87.5 s → 35.7 s; 500 cells 385.9 s → 164.0 s; total blocking time 279.9 s → 78.5 s.
- **Why it is slow:** every style-sheet rewrite (F1) invalidates every running keyframe animation, and each animation
  also needs a style update per frame on the main thread. The number of bars is proportional to the cells still waiting,
  and so is the number of mounts: O(cells²). Hidden markdown cells get bars too, although they are `h-0`.
- **Proposed fix:** remove the pulse from the bars (`patches/frontend-browser-code-placeholder-no-pulse.patch`). If a
  shimmer is wanted, animate one wrapper per cell, or only placeholders inside the viewport, and render nothing for
  placeholders with `h-0 overflow-hidden`.
- **Expected impact:** −57% to −60% of load main-thread time on its own; with F1, 500-cell style time 276.6 s → 4.3 s.
- **Effort / risk:** S. Visual change only.

### F3. Every cell subscribes to the document sync status and re-renders 2–3 times per keystroke

- **Category:** `datastructures`, `batching`
- **Where:** `frontend/src/core/saving/document.ts:21` (`useNotebookDocumentSave` calls `useNotebookDocumentSync()`),
  `frontend/src/core/notebook/document/hooks.tsx:114-118` (`useNotebookDocumentSync` does `useAtomValue(model.syncStatusAtom)`
  and returns `flush`), reached per cell through `useSaveNotebook()` (`frontend/src/core/saving/save-component.tsx:102`) in
  `frontend/src/components/editor/navigation/navigation.ts:204` (`useCellNavigationProps`) and
  `frontend/src/components/editor/cell/code/cell-editor.tsx:128` (`CellEditorInternal`).
- **Evidence:** MEASURED with the why-recorder: for 30 keystrokes at 250 cells, `EditableCellComponent` renders 10,988 times and
  `CellEditorInternal` 11,032 times, each because of this atom; at 500 cells 47,750 component renders per keystroke.
  The same atom re-renders every cell on add, delete, move, hide, run-one, focus and after autosave. Fix prototyped:
  typing at 250 cells 323 → 88 ms of work per key, key→paint p95 328 → 65 ms, long tasks 16 → 5 per 20 keys.
- **Why it is slow:** saving only needs `flush`, but the hook also subscribes to the status, which flips 2–3 times per
  edit. Each flip re-renders N cells, each with ~60 child components (tooltips, buttons, menus).
- **Proposed fix:** a `useNotebookDocumentFlush()` that returns `useDocumentModel().flush` and no status
  (`patches/frontend-browser-save-without-sync-status-subscription.patch`). Keep `useNotebookDocumentSync` for the footer and save button.
- **Expected impact:** −73% main-thread work per keystroke at 250 cells; removes the all-cell re-render from every edit interaction.
  The work in the 2.5 s after typing stops at 500 cells falls from 1.9–2.3 s to 0.3–0.5 s (with F4, F5).
- **Effort / risk:** S. No behaviour change: `flush` is already stable.

### F4. `layoutAtom` changes identity on every document change, re-rendering the cell list and every `SortableCell`

- **Category:** `datastructures`, `caching`
- **Where:** `frontend/src/core/cells/layout.ts:144` (`layoutAtom` reads `model.documentAtom` and builds a new `Layout`);
  consumers `frontend/src/components/editor/renderers/cell-array.tsx:48`, `:103`, `:174`; `:204` passes
  `items={[...column.visible]}` to dnd-kit's `SortableContext`.
- **Evidence:** MEASURED. `CellArray`, `CellArrayInternal`, `CellColumn` render 3 times per keystroke because of `layoutAtom`;
  `SortableCell` renders 22,250 times per 30 keystrokes at 250 cells because the sortable context's `items` changed.
  Prototype on top of F3: 88 → 53 ms per key at 250 cells, zero long tasks.
- **Why it is slow:** the document object changes when any cell's code changes, although the order, columns and folds do not.
- **Proposed fix:** keep the previous `Layout` when it is structurally equal (`patches/frontend-browser-layout-atom-stable-identity.patch`),
  or better, derive it from a structure-only atom (order + column breaks) so it does not recompute at all on code edits.
  Memoize `column.visible` instead of spreading it on each render.
- **Expected impact:** −40% of the remaining per-keystroke work after F3.
- **Effort / risk:** S. The equality check is O(cells) string compares per document change.

### F5. `isInVscodeExtension()` scans the whole document on every portal render

- **Category:** `caching`, `algorithms`
- **Where:** `frontend/src/core/vscode/is-in-vscode.ts:8` (`document.querySelector("[data-vscode-theme-kind]")`), called on
  every render from `frontend/src/components/ui/fullscreen.tsx:149` (`withFullScreenAsRoot`) and `:200`
  (`withSmartCollisionBoundary`), which wrap the portals and contents of tooltips, context menus, dropdowns, popovers and selects.
- **Evidence:** MEASURED at 500 cells: 29.8 s of 105.9 s while typing 30 characters (28.1%), 8.1 s of 39.0 s adding 3 cells (20.8%),
  10.6 s during run-all (10.8%). At 250 cells it is 15.7% of typing, so the share grows with size.
- **Why it is slow:** outside VS Code nothing matches, so each call walks all 91,027 elements. It runs once per portal
  wrapper render (772 per keystroke at 500 cells): O(renders × DOM size).
- **Proposed fix:** read the attribute where VS Code sets it instead of scanning
  (`patches/frontend-browser-is-in-vscode-without-document-scan.patch`; INFERRED that it is on `<body>`), or compute it once at startup.
- **Expected impact:** −20% to −28% of script in typing and add-cell at 500 cells before F3/F4; after them the wrappers
  rarely render, so the gain is smaller (53 → 50 ms per key at 250).
- **Effort / risk:** S. Check the VS Code webview before changing where the attribute is read.

### F6. Each incoming stream event recomputes every cell's derived state

- **Category:** `batching`, `datastructures`, `caching`
- **Where:** `frontend/src/core/transports/server.ts:112` (one handler call per WebSocket message) →
  `frontend/src/core/notebook/replica/replica.ts:417` (`apply`) → `:266` (`setStream`, `store.set(followedAtom, …)`).
  Per-cell readers that rerun for every event: `frontend/src/core/executions/hooks.ts:29-41` (`useCellExecution`,
  `selectAtom(cellExecutionInputsAtom, …, dequal)`), `:50-56` (`useCellFreshness`), `frontend/src/core/cells/cells.ts:573-585`
  (`cellRuntimeAtom`), `frontend/src/core/executions/select.ts:166` (`cellExecutionView`, which parses ISO timestamps with
  `frontend/src/utils/time.ts:35` on every call).
- **Evidence:** MEASURED. Handler time per `execution` event: 0.7 ms at 25 cells, 13.7 ms at 500 (exponent 2.15 for the total:
  0.1 → 27.3 s). Run-all at 500 cells: 45.5 s of 97.6 s (46.5%) inside this path, 39.0 s in jotai's
  `recomputeInvalidatedAtoms`; `cellExecutionView` 4.9 s, `Time.parse` 2.7 s. After F1–F5 it is the largest remaining load cost:
  26.2 s of the 38.4 s of script at 500 cells at 1×, and 102.6 s of 153.0 s at 4×. With CPU at 4×, 250 cells need 120–130 s
  for a run that completes in 17 s at 1×.
- **Why it is slow:** 3 execution events and 1 output event arrive per cell, each in its own task. Each sets one store
  atom, and jotai then reruns the selector of every mounted cell: O(cells) per event, O(cells²) per run.
- **Proposed fix:** (1) coalesce events that arrive in the same frame into one `store.set` (queue in `apply`, flush in a
  microtask or `requestAnimationFrame`). (2) Give each cell an atom over its own record (`executions.latest.get(id)` /
  `results.get(id)`) so an event for cell A does not rerun cell B's selector; keep `dequal` only as a last guard.
  (3) Store parsed milliseconds on the record once instead of calling `Date.parse` per cell per event.
- **Expected impact:** INFERRED: run-all script at 500 cells roughly halves (−40 s of 80 s on the profiling build); load script after F1–F5 38 s → ~15 s.
- **Effort / risk:** M. Batching changes when intermediate states (queued → running) become visible; keep ordering within a batch.

### F7. Per-cell React subtree is large, and nothing below the cell bails out

- **Category:** `lazy-init`, `datastructures`
- **Where:** `frontend/src/components/editor/notebook-cell.tsx:371` (`EditableCellComponent`),
  `frontend/src/components/editor/cell/cell-context-menu.tsx:51`, `frontend/src/components/editor/cell/cell-actions.tsx:58`,
  `frontend/src/components/editor/SortableCell.tsx:47`, `frontend/src/components/ui/tooltip.tsx:16-19`.
- **Evidence:** MEASURED. One cell re-render renders ~62 components (47,750 / 768 at 500 cells), including 4 `Button`, 3 `Tooltip`
  with `Popper`/`Presence`, a context menu and a dropdown that are closed. 182 DOM elements and 170 listeners per cell.
  react-dom objects are 35.0 MB of a 108.9 MB heap at 100 cells; radix 6.8 MB.
  Radix `Presence` calls `getComputedStyle` on mount (`@radix-ui/react-presence` `getAnimationName`): 1.2 s self during a 500-cell load, 8 forced recalcs in the 4 s trace.
- **Why it is slow:** every cell mounts tooltip, popper, context-menu and dropdown machinery up front, and the children are
  recreated whenever the cell renders, so any cell-level state change costs ~60 component renders.
- **Proposed fix:** mount tooltip/context-menu/dropdown content on first hover, focus or open (a thin trigger until then);
  put a memo boundary at the cell's toolbar and at `OutputArea`/`ConsoleOutput` so a status change does not re-render them.
  Longer term, virtualize offscreen cells (keep the editor state, drop the DOM).
- **Expected impact:** INFERRED: −30% to −50% heap and DOM per cell; makes every remaining all-cell re-render ~3× cheaper.
- **Effort / risk:** M–L. Lazy tooltips need care for keyboard focus and tests that query tooltips.

### F8. `useCellActions()` creates ~35 hooks per call and is called ~10 times per cell

- **Category:** `caching`, `datastructures`
- **Where:** `frontend/src/core/cells/actions.ts:655` (`useCellActions`: `useReducerActions()` + 33 `useSetAtom` + `useMemo`).
  Called from 38 sites, per cell at `notebook-cell.tsx:402`, `:835`, `:989`, `navigation.ts:207` and `:208` (twice in one hook),
  `cell-editor.tsx:134`, `useDeleteCell.tsx:12` and `:43`, `useCellActionButton.tsx:99`, `useSplitCell.tsx:12`, `useAnswerPrompt.ts:13` and others.
- **Evidence:** MEASURED. 7.6 s inclusive of 105.9 s while typing at 500 cells (7.2%), 6.7% of add-cell; `useSetAtom` 2.3 s self.
  Heap: `useSetAtom` 13.6 MB self and `useCellActions` 18.0 MB inclusive at 100 cells (17% of the heap).
- **Why it is slow:** each call allocates 33 callbacks and hook slots and re-validates them on every render.
- **Proposed fix:** build the actions object once per store (for example a `WeakMap<Store, CellActions>` or a single atom
  holding bound actions) and have `useCellActions` return it after one `useStore()`. Remove the duplicate call in `navigation.ts:207-208`.
- **Expected impact:** −7% script per all-cell render; −15% heap (≈ −70 MB at 500 cells).
- **Effort / risk:** S–M. The returned object must stay referentially stable, which it already is per component.

### F9. Clearing the pending-delete state re-renders every cell on each selection change

- **Category:** `datastructures`
- **Where:** `frontend/src/core/cells/pending-delete-service.ts:120` (`clear: () => initialState()` returns a new object
  every time), subscribers `:127` (`usePendingDeleteService`, used per cell in `cell-editor.tsx:129` and `navigation.ts:216`) and
  `:141` (`usePendingDelete`, per cell in `frontend/src/components/editor/cell/PendingDeleteConfirmation.tsx:16`).
  `clear()` is called on every selection change at `frontend/src/components/editor/navigation/navigation.ts:224`, `:228`, `:232`.
- **Evidence:** MEASURED. Six arrow keys in command mode at 250 cells: 23 commits, 90,819 component renders;
  `CellEditorInternal` 1,506 and `PendingDeleteConfirmation` 1,500 renders, all from this atom. Latency per arrow key:
  31 / 154 / 229 / 1,875 ms at 25 / 100 / 250 / 500 cells (11.7 s at 4×). Still 416 ms at 500 with F1–F5 applied.
- **Why it is slow:** the atom's value is a fresh `{ entries: new Map() }` on every clear, and every cell reads the whole state.
- **Proposed fix:** return the same state when it is already empty (`patches/frontend-browser-pending-delete-stable-clear.patch`, not validated in a build),
  and subscribe per cell with a selector (`entries.get(cellId)`, `entries.size`).
- **Expected impact:** arrow-key navigation becomes independent of the cell count (INFERRED: ~30 ms).
- **Effort / risk:** S.

### F10. All 501 editors are built although 3 are visible and 250 are never shown

- **Category:** `lazy-init`
- **Where:** `frontend/src/components/editor/cell/code/cell-editor.tsx:385-408` (every cell requests a build),
  `frontend/src/core/codemirror/editor-mount-scheduler.ts:58` (one build per task, no idle or visibility condition),
  `cell-editor.tsx:450-452` (hidden markdown editors get `h-0 overflow-hidden` but are still built).
- **Evidence:** MEASURED: after load, 501 `.cm-editor`: 250 in hidden-code markdown cells, 248–249 offscreen, 3 in the
  viewport; 12 `.cm-line` per cell; at 4× CPU only 4 editors mounted during a 170 s run.
  INFERRED from the listener target/type table: ≈ 70 of the cell's 156 `addEventListener` calls belong to the editor
  (26 content handlers, scroll listeners on 13 ancestors, 6 window/document listeners). INFERRED by proportion: before F1/F2
  the hidden editors are half of the quadratic style cost (≈ 130 of 260 s at 500); after F1/F2 the builds cost a few seconds
  of script at 500 cells (at 250 cells `cell-editor.tsx:329` is 41.6 s inclusive, 41.1 s of it the constructor's forced style recalc).
- **Why it is slow:** building is unconditional; the queue only orders it.
- **Proposed fix:** build an editor when its cell is within ~2 viewports or is focused/targeted (the scheduler already has
  `promote`), and never for a `hide_code` cell until its code is shown; keep the lightweight placeholder otherwise.
  Notebook-wide find and "go to definition" must then work on document text (see F11) or promote on demand.
- **Expected impact:** load at 500 cells mounts ~10 editors instead of 501; listeners 85k → ~50k; heap −5% to −10%.
- **Effort / risk:** M. Features that iterate `getAllEditorViews()` (`frontend/src/core/cells/cells.ts:619`) assume every editor exists.

### F11. Notebook-wide find dispatches to every editor and forces a layout per editor

- **Category:** `algorithms`, `batching`
- **Where:** `frontend/src/core/codemirror/find-replace/search-highlight.ts:21-23` (`setGlobalSearchQuery` loops over
  `getAllEditorViews()`), `:45-46` (`clearGlobalSearchQuery`), `frontend/src/components/find-replace/find-replace.tsx:60-76`.
- **Evidence:** MEASURED. Mod-F at 500 cells: 8.9 s to focus the input (1×), LayoutDuration 8.36 s in 2 layouts; 13.9 s at 4×.
  Typing the query: 1.1 s of work per key at 500 (exponent 1.15). Profile at 250 cells: CodeMirror `measure` 655 ms inclusive,
  `getBoundingClientRect` 520 ms self, 1,023 React commits because each editor's panel is its own root (`LanguagePanelComponent` 1,000 renders).
- **Why it is slow:** every keystroke in the find box updates N editor states; each view then measures itself, interleaving
  DOM writes and layout reads across N views.
- **Proposed fix:** search the document text once (strings), keep match ranges in an atom, and dispatch highlight effects
  only to editors that are visible or contain the current match; batch the dispatches inside one frame.
- **Expected impact:** INFERRED: find open < 200 ms and typing < 100 ms per key at 500 cells.
- **Effort / risk:** M.

### F12. One global listener per component instance: 170 listeners per cell

- **Category:** `dom-listeners`
- **Where:**
  - `frontend/src/components/ui/button.tsx:131`: every `Button` adds a `document` `keydown` listener, with or without a
    `keyboardShortcut` (8 per cell, 4,044 at 500).
  - `frontend/src/components/ui/fullscreen.tsx:64` (`useFullScreenElement` inside `withFullScreenAsRoot`'s `Comp`, `:146`):
    one `document` `fullscreenchange` listener per portal wrapper (12 added per cell, 6,043 at 500). `:82` already has a shared-listener pattern (`subscribeToFullScreen`, used by `useIsFullScreen`).
  - `frontend/src/core/codemirror/go-to-definition/underline.ts:66-69`: `window` `keydown`, `keyup`, `blur`, `mouseleave` per editor (2,004 at 500).
  - CodeMirror's own scroll listeners on every scrollable ancestor (13 per editor, 6,507 at 500) and 1 `MediaQueryList` listener per editor.
- **Evidence:** MEASURED counts above. Time in all keydown listeners per keystroke: 0.3 / 0.6 / 1.2 / 2.7 ms at 25 / 100 / 250 / 500 cells.
- **Why it is slow:** each event calls N handlers that return immediately; the cost is small per event but linear, and the listeners hold memory.
- **Proposed fix:** register the `Button` listener only when `keyboardShortcut` is set
  (`patches/frontend-browser-button-keydown-listener-only-with-shortcut.patch`); use the existing shared `subscribeToFullScreen`
  store in `useFullScreenElement`; register one window-level modifier-key tracker for go-to-definition and let editors read it.
- **Expected impact:** −24 global listeners per cell (−12,000 at 500); −2.5 ms per keydown.
- **Effort / risk:** S.

### F13. `ConsoleOutput` reads layout in an effect with no dependency list

- **Category:** `batching`
- **Where:** `frontend/src/components/editor/output/console/ConsoleOutput.tsx:134-149` (`useLayoutEffect` without deps reads
  `scrollHeight`, `clientHeight`, `scrollTop`).
- **Evidence:** MEASURED. 3.8 s self during a 500-cell load, 1.2 s at 250, 0.5 s while typing 30 characters at 500;
  7 forced style recalcs and 7 forced layouts in the 4 s load trace.
- **Why it is slow:** the read runs for every cell on every render, in the commit phase right after DOM writes, so the first read forces layout.
- **Proposed fix:** skip the effect when the cell has no console output, and depend on the output length.
- **Expected impact:** −1% of load script; removes a forced layout from every all-cell commit.
- **Effort / risk:** S.

### F14. Opening a dialog restyles the whole document

- **Category:** `css-selectors`
- **Where:** `frontend/src/components/editor/controls/command-palette.tsx:37` (trigger); cause INFERRED: the dialog changes
  attributes on `body`/root, and rules such as `:root:has(body.dark)` and `.marimo-cell:has(.mo-ai-deleted-cell) .cm-content`
  make root-level changes invalidate descendants.
- **Evidence:** MEASURED. Mod-K at 500 cells: 1.89 s to the first item, RecalcStyleDuration 1,428 ms in 18 recalcs
  (112 / 405 / 785 / 1,892 ms at 25 / 100 / 250 / 500). In selector stats those two `:has()` rules are the 2nd and 3rd most
  expensive selectors despite 18–330 match attempts.
- **Why it is slow:** a full recalc costs ~15 µs per element and there are 91,027 elements.
- **Proposed fix:** replace `:root:has(body.dark)` with a class on `:root`; scope the `.mo-ai-deleted-cell` rule with a class
  set on the cell; reduce the DOM (F7, F10). Verify with a trace which attribute change triggers the recalc.
- **Expected impact:** INFERRED: palette open < 300 ms at 500 cells.
- **Effort / risk:** S–M.

### F15. Scroll and resize do work proportional to the cell count

- **Category:** `dom-listeners`, `batching`
- **Where:** INFERRED from listener counts and traces: CodeMirror scroll listeners on ancestors (every scroll of `#App`
  calls 501 handlers), `frontend/src/components/editor/notebook-cell.tsx:494` (`useResizeObserver` per cell),
  `cell-editor.tsx:433` (`useIntersectionObserver` per cell).
- **Evidence:** MEASURED. Wheel-scrolling for 6 s costs 0.4 / 2.2 / 3.5 / 6.2 s of main-thread time at 25 / 100 / 250 / 500 cells;
  at 500 cells 10 fps with 9 long tasks (4.8 s). In the 100-cell trace, 73 of 165 style recalcs during scroll were forced from
  CodeMirror's `measure` and scroll handler. Resize at 500: 0.85–0.93 s, script 1.9–2.1 s, layout 0.22–0.24 s.
  The 500-cell scroll number was taken after other scenarios and may include their leftover work.
- **Why it is slow:** every editor reacts to every scroll and resize.
- **Proposed fix:** F10 removes most editors; then re-measure. `content-visibility: auto` on cells is worth a real design (it cut load style time by 92% in M7).
- **Expected impact:** not quantified.
- **Effort / risk:** M.

### F16. Memory: 0.9 MB of JS heap, 284 DOM nodes and 170 listeners per cell

- **Category:** `datastructures`, `lazy-init`
- **Where:** see F7, F8, F10.
- **Evidence:** MEASURED in M8: 458 MB at 500 `smoke` cells, 518 MB for `outputs`. No leak across run-all passes.
- **Why it is slow:** GC is 5–7% of script in typing, add-cell and run-all at 500 cells.
- **Proposed fix:** F7, F8, F10.
- **Expected impact:** INFERRED: −40% heap with all three.
- **Effort / risk:** as above.

## Ruled out

- **CSS selector matching.** 3.4–4.3% of style-recalc time in every traced scenario (401 ms of 11.8 s mid-load). `:has()` is 8–14% of
  that. The cost is how many elements are restyled, not how selectors are written.
- **Layout during load.** 2.4 s of 352 s at 500 cells (0.7%).
- **React during load.** 4.6% of load CPU at 500 cells; 11.5 s of render time over 1,444 commits.
- **Markdown rendering and JSON parsing.** < 0.1% in all four 500-cell profiles (Lezer markdown `toTree` 56 ms at 250 cells).
- **Message size.** 1.5 MB over 2,783 messages for a 500-cell load; the time is in applying them (F6), not parsing.
- **Save payload.** `POST …/save` carries 2 bytes; edits are deltas of 79–1,785 bytes. Save latency at 500 cells (1.4 s) is
  the backend plus F3's re-render.
- **Memory leak.** +10 MB after the first run-all at 500 cells, then +1 MB per run-all; DOM nodes flat.
- **DOM depth.** 30 at every size. `<style>` elements: 3 at every size.
- **Sidebar panels.** Variables, outline, documentation and dependencies open in 72–354 ms at 500 cells, and typing with
  any of them open costs the same as without (848–1,220 vs 901–943 ms per key).
- **Position in the notebook.** Typing near the top, middle and bottom costs the same (695 / 917 / 614 ms at 500 cells).
- **DOM-only virtualization for typing.** `display: none` on all but 17 cells: 637 ms per key vs 577 ms. The cost is React and script.
- **CodeMirror's own input handling.** `beforeinput`→`input` is 6 ms at 25 cells and 17 ms at 500 cells once F3–F5 are applied.

## Benchmarks added

- `frontend/benchmarks/notebook-load.browser.ts` (new): load timing for any notebook URL — first/last cell and editor,
  long tasks, CDP task/script/style/layout durations, DOM nodes, listeners, heap. Run:
  `node benchmarks/notebook-load.browser.ts 'http://127.0.0.1:29871/?file=browser-500.py' ../.context/load-results`
  (`LOAD_BENCH_RUNS`, `LOAD_BENCH_RATES`, `LOAD_BENCH_TIMEOUT`). Checked with `oxfmt` and one run at 25 cells.
- `frontend/benchmarks/create-editing-fixtures.ts`: `--cells=25,100,250,500` option (default unchanged).
- `frontend/benchmarks/cell-editing.md`: "Large notebooks" and "Notebook load" sections.
- Scratch tooling, not for merging as is (`.context/perf/frontend-browser/`): `lib.ts` (page probe: listeners, observers,
  WebSocket handler time, long tasks, fetches; `serveBuild` to test a build without touching `_static`), `load.ts`,
  `interact.ts` (about 35 interaction scenarios), `trace.ts` (CPU profile, timeline trace, selector stats, React commits),
  `why-recorder.ts` (which hook/atom/context caused each render — worth promoting next to `react-commits.ts`),
  `analyze-profile.ts`, `analyze-trace.ts`, `memory.ts`, `heap.ts`, `vite.perf-experiment.mts` (prototype fixes at build time).
- Patches: `../patches/frontend-browser-*.patch` (8 files). Other investigators wrote overlapping patches for the
  shared themes, the sync subscription, the VS Code check and the button listener; the measurements here apply to those too.

## Not measured

- 1000 cells: the load did not finish (run-all incomplete after 600 s; a second attempt was stopped after 52 minutes).
- 4× CPU at 500 cells on the unpatched build: load (run-all incomplete at 600 s) and typing, create, palette (the editor
  could not be focused within 30 s). 4×/250 load is a single run.
- Detached DOM nodes by heap snapshot (only CDP counters).
- Firefox and Safari; a real GPU compositor (headless shell).
- The exact attribute change behind F14, and a clean attribution of scroll cost (F15).
- `marimo/_static/` was not rebuilt or modified, so no restore was needed; all servers and browsers started here were stopped.
