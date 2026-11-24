# Frontend state and React render fan-out — large-notebook performance

Scope: `frontend/src` state (Jotai store, notebook reducer, host-stream replica, document model),
kernel-event handling, and which React components render when. No browser was run here; where a
browser number matters, it is quoted from the browser investigator's captures and labelled as theirs.

**Read this first.** The state layer is not the old `cell-op` reducer the brief describes. Cells live
in a host *document* (`core/notebook/document`, drafts over a confirmed revision), kernel activity
arrives as a typed *event stream* (`core/notebook/replica` → `core/executions`), and `notebookAtom`
(`core/cells/cells.ts`) is a follower kept in step by `applyDocument`
(`core/cells/document.ts`, marked `TODO(MO-8349)` for deletion). Findings are mapped to that code.

**Machine load.** Other investigators ran concurrently: `uptime` load average was 30–430 on 14 cores
for every run below. Absolute milliseconds are inflated: real Chromium spends 9.85 ms per stream
message at 500 cells (M1 cross-check) where this harness measured 31 ms per event. Counts, ratios,
and scaling exponents are the evidence.

## Measurements

All commands run from `frontend/`. `SCRATCH=../.context/perf/frontend-state`. Scratch tests run with
`pnpm exec vitest run --config $SCRATCH/vitest.config.ts <name>`; raw results are JSON files there.

### M1. Store cost per event, by notebook size (jsdom, no React)

`probe.test.ts` → `probe-50-100-250-500.json`. Median of 3 (15–31 for the single-event rows).
Fixture: setup cell + alternating hidden-markdown / 1 KB code cells, star dependency graph
(`benchmarks/large-notebook-state.fixture.ts`). "Mounted" = the atoms one `EditableCell` subscribes
to, × n, plus the notebook chrome's (`mount()` in the fixture). A run-all here is a re-run: 5n+8
events (`run` × 3, and per cell `execution.removed`, `queued`, `running`, `output`, `completed`).
The shape follows a real server capture by the wire-protocol investigator
(`wire-protocol/trace-explore-100.jsonl`: 4 stream events per cell on a first run).

| ms | 50 | 100 | 250 | 500 | exponent 100→500 |
| --- | --- | --- | --- | --- | --- |
| Run-all, **one store update per event** (shipped), mounted | 512 | 1,337 | 17,771 | **78,699** | 2.53 |
| Run-all, **one store update per batch** (prototype), mounted | 8.4 | 13.2 | 68 | **286** | 1.91 |
| Run-all, per event, nothing mounted | 8.1 | 16.7 | 73 | 312 | 1.82 |
| Run-all, pure reducer only (`reducer.reduce` over the events) | 1.3 | 3.5 | 20 | 125 | 2.22 |
| Run-all, protocol validation only (zod, 5n+8 events) | 6.3 | 4.6 | 8.9 | 24 | 1.02 |
| Snapshot (n `cell` events), pure reducer only | 0.21 | 0.52 | 2.4 | 12.2 | 1.96 |
| One cell's lifecycle (5–6 events), per event, mounted | 10.1 | 12.7 | 88 | 112 | 1.35 |
| One cell's lifecycle, per event, nothing mounted | 0.12 | 0.12 | 0.18 | 0.32 | 0.62 |
| One keystroke (`editAtom` → `setCode`), mounted | 0.83 | 1.27 | 5.9 | 12.7 | 1.43 |
| One keystroke, nothing mounted | 0.08 | 0.12 | 0.24 | 0.56 | 0.97 |

Cross-check in real Chromium (browser investigator's data, not mine:
`frontend-browser/out/load/base-smoke-*-cpu1-run*.json`, field `ws`, median of runs, no CPU throttle):

| cells | WS messages | time inside the WS `message` handler | per message | DOM elements |
| --- | --- | --- | --- | --- |
| 25 | 170 | 97 ms | 0.57 ms | 5,200 |
| 50 | 308 | 255 ms | 0.83 ms | 9,785 |
| 100 | 583 | 859 ms | 1.47 ms | 18,739 |
| 250 | 1,408 | 5,850 ms | 4.15 ms | 45,971 |
| 500 | 2,783 | **27,408 ms** | 9.85 ms | 91,027 |

Exponent 100→500 = 2.15; at 500 cells, `execution` events are 1,503 × 13.7 ms and `output` events
501 × 12.9 ms. That is 47% of that load's 58.3 s `ScriptDuration`.

### M2. CPU profile of a per-event run-all (250 cells, mounted)

`PROFILE_N=250 … profile` → `run-all-per-event-250.profile.txt` (+ `.cpuprofile`). 16.0 s wall.
Inclusive: `setStream` (replica.ts) 79.8%, of which Jotai `recomputeInvalidatedAtoms` 76.9%;
`observeExecution` → `startCellConsole` dispatch 8.2%. Self: Jotai internals
(`readAtomState` 16.9%, `recomputeInvalidatedAtoms` 15.8%, `ensureAtomState`, `getter`,
`invalidateDependents`, `getMountedOrPendingDependents`, `mountDependencies` ≈ 54% together), GC 7.7%,
`Time.parse` 2.7%, `dequal` 2.4%, `cellExecutionView` + `latestOf` 2.4%, freshness 3.5%.
`keystroke-500.profile.txt`: 85% of a keystroke is `followDocument` → `reconcileDocument` →
recomputing everything derived from `notebookAtom`.

### M3. Which subscribers are notified (500 cells)

`fanout.test.ts` → `fanout-500.json`. `store.sub` callbacks fired per action; "cell:" rows are summed
over all 500 cells. Each callback is one React re-render of each `useAtomValue` reader.

| action | per-cell atoms notified | notebook-wide atoms notified |
| --- | --- | --- |
| one keystroke | `cellDataAtom` 1, code binding 1 | `notebookAtom`, `model.documentAtom`, **`layoutAtom`**, **`cellErrorsAtom`**, `renderedNotebookCellsAtom`, `notebookCellCodes`, `syncStatusAtom` (see M4) |
| host confirms the edit (`cell` + `document` + `analysis`) | `cellRuntimeAtom` 1, freshness 1 | `cellExecutionInputsAtom` ×2, `cellFreshnessAtom`, `cellOutputInputsAtom`, `cellOutputsAtom`, **`layoutAtom`**, `runReasonAtom`, `needsRunAtom`, `needsSaveAtom`, `documentVersionAtom`, `notebookAnalysisAtom`, `syncStatusAtom` ×2 |
| cell → queued | execution view 1, `cellRuntimeAtom` 2 | `cellExecutionInputsAtom` ×2, `cellFreshnessAtom` ×2, `cellOutputInputsAtom` ×2, `cellOutputsAtom` ×2, queued/running count |
| cell → running | execution view 1, `cellRuntimeAtom` 1 | the four inputs atoms, **`notebookAtom`**, `cellErrorsAtom`, `notebookIsRunningAtom` |
| markdown cell → output, then → completed (same HTML) | `cellOutputAtom` **2**, `cellOutlineAtom` **2**, execution view 1 | the four inputs atoms ×2, `cellErrorsAtom` ×2, **`notebookOutline` ×2** |
| code cell → output, → completed | execution view 1 | the four inputs atoms ×2 |

So notification is well targeted per cell. The cost in M1 is *recomputation*: every event re-reads
O(n) selectors to discover that 499 of them did not change.

### M4. Which components render (jsdom, real `<Cell>` components, React `Profiler` per cell)

`renders.test.tsx` → `renders-<proto>-<n>.json`; `RENDERS_N=30|60|120`, `PROTO=base|vscode|sync`.
Counts are deterministic and identical in shape at every n. Milliseconds are jsdom + dev React under
load, shown only for the two prototypes run back to back.

| scenario (n = 120) | cells that re-render | `useCellActions()` calls | `querySelector("[data-vscode-theme-kind]")` calls |
| --- | --- | --- | --- |
| mount | 120 (5 renders each) | 73.8 per cell | 16.4 per cell |
| first keystroke after idle (sync status idle → pending) | **120 of 120**, 2 commits each | 2,399 | 361 |
| second keystroke inside the 100 ms batch window | 1 | 20 | 3 |
| batch window elapses (pending → sending) | **120 of 120**, 2 commits each | 2,399 | 365 |
| one code cell queued / running / completed | 1 each (2 commits) | 25 / 25 / 25 | 8 / 8 / 8 |
| one markdown cell sets output / completes | 1 / 1 | 15 / 25 | 2 / 8 |
| `SortableContext` parent re-renders with a new array of the same ids | **120 of 120** `SortableCell`s (children 0) | – | – |
| `FloatingOutline`: one markdown cell re-runs, same output (60 headings) | 2 renders | – | 120 `querySelectorAll('[id=…]')` |

Prototype effect, same harness (ms for the whole `act()`):

| n | first-keystroke wave, base | with `isInVscodeExtension` memoized | one cell queued, base | memoized |
| --- | --- | --- | --- | --- |
| 30 | 1,753 | 84 | 138 | 8.5 |
| 60 | 5,336 | 129 | 177 | 10.3 |
| 120 | 13,747 | 381 | 586 | 25.4 |

With `useNotebookDocumentSave` no longer subscribed to the sync status (`PROTO=sync`), the first
keystroke re-renders 1 cell instead of n, and the pending → sending transition re-renders 0.
`cell-event-react-60.profile.txt`: in the base case 80.5% of a one-cell status change is
`isInVscodeExtension` → `document.querySelector` (jsdom's selector engine is far slower than
Blink's; the ratio is not transferable, the O(DOM) shape is).

### M5. Hot functions (jsdom, nothing mounted)

`micro.test.ts` → `micro.json`, median of 5–15.

| function | 500 cells | 2,000 cells |
| --- | --- | --- |
| `cellExecutionView` × n, idle notebook | 0.68 ms | 3.07 ms |
| `cellExecutionView` × n, a `cells` run that has planned none (`awaited`) | 3.30 ms | 36.5 ms |
| `Time.parse` × 4n (what `cellExecutionView` × n parses) | 0.32 ms | 2.40 ms |
| `runs.addExecution` for one run-all (3n calls) | 42.7 ms | 1,057 ms |
| `cellErrorsAtom` recompute | 0.63 ms | 1.93 ms |
| `cellIdToNamesMap` recompute | 0.31 ms | 0.97 ms |
| `startCellConsole` reducer (spread of `cellRuntime`) | 0.001 ms | 0.62 ms |
| LSP `createNotebookLens` (merge every cell) | 0.41 ms | 1.41 ms |
| LSP `didChange` payload size | 426 KB | 1,705 KB |
| `sameShown` (2 × `JSON.stringify`) on a 10 KB / 100 KB / 1 MB output | 0.009 / 0.05 / 3.6 ms | – |

`console.test.ts` → `console.json`: one live `console` (stdout) event for a running cell, mean of 300.

| ms per stdout line | 100 cells | 500 cells |
| --- | --- | --- |
| stream event only, mounted | 2.9 | 18.2 |
| stream event + `addLogs` (what `consoleObservers.onItem` adds), mounted | 5.5 | 23.8 |
| stream event + `addLogs`, nothing mounted | 0.11 | 0.09 |

### M6. `large-notebook-state.bench.ts`

`bench-run{1..4}.json` (command under "Benchmarks added"). Median of the per-run p50 latency
over 4 runs, with the range across runs; a spread of 2–5× is machine load.

| group | benchmark | 500 cells, ms | 2,000 cells, ms | exponent |
| --- | --- | --- | --- | --- |
| load | snapshot, validation only | 11.9 (2.58–48.7) | 8.86 (8.16–13.6) | -0.21 |
| load | snapshot, reducer only | 49.5 (7.98–120) | 233 (191–287) | 1.12 |
| typing | one keystroke | 25.6 (9.61–46.9) | 59.0 (39.1–88.6) | 0.60 |
| typing | one confirmed edit | 122 (35.1–149) | 305 (160–579) | 0.66 |
| typing, by step | viewDocument | 0.027 (0.025–0.028) | 0.125 (0.121–0.182) | 1.12 |
| typing, by step | toChanges | 0.039 (0.034–0.134) | 0.187 (0.150–0.253) | 1.13 |
| typing, by step | applyDocument | 0.322 (0.260–0.497) | 2.14 (1.06–3.22) | 1.36 |
| kernel events | one cell runs, per-event | 212 (89.8–680) | 744 (309–1,358) | 0.91 |
| kernel events | one cell runs, batched | 26.2 (25.5–39.3) | 200 (82.4–935) | 1.47 |
| kernel events | every cell runs, batched | 197 (163–211) | 3,934 (2,820–16,430) | 2.16 |
| kernel events | every cell runs, reducer only | 112 (79.4–135) | 3,734 (1,859–8,573) | 2.53 |
| selectors | cellExecutionView for every cell | 0.463 (0.385–0.570) | 3.79 (2.58–8.30) | 1.52 |
| selectors | freshness for every cell | 0.289 (0.243–0.409) | 3.25 (2.51–4.67) | 1.75 |
| selectors | cellOutputsView | 0.217 (0.204–0.231) | 2.50 (1.37–7.55) | 1.76 |
| selectors | notebookRunReason | 0.538 (0.442–0.590) | 3.65 (3.05–6.15) | 1.38 |
| selectors | queuedOrRunningCount | 0.004 (0.003–0.004) | 0.017 (0.016–0.019) | 1.06 |
| selectors | deriveLayout | 0.132 (0.112–0.157) | 0.932 (0.664–1.09) | 1.41 |
| structure | create and delete a cell at the top | 38.4 (35.4–41.4) | 247 (197–1,238) | 1.34 |
| structure | move the top cell down and up | 56.3 (42.8–67.0) | 334 (289–357) | 1.28 |
| kernel events | every cell runs, per-event | 90,331 (59,340–343,688) | – | – |

- Every cell runs, 500 cells: 59.3–344 s with one store update per event
  (3 single-sample runs) vs 197 ms batched: 302–1,749×.
- Batched run-all vs the pure reducer alone, per run: 189/115, 163/79, 211/135, 204/109 ms at 500 cells
  and 2,820/1,859, 3,717/2,140, 16,430/8,573, 4,150/5,327 ms at 2,000. Once events are batched, the
  reducer's per-event map copies are half or more of what is left, and they are quadratic (F7).
- One confirmed edit (three events) costs 122 ms at 500 cells; one keystroke 25.6 ms, of which
  `viewDocument` + `toChanges` are 0.065 ms.
- The structure rows are two edits per sample (create + delete, down + up).
- The per-event "every cell runs" case is one sample per run and is skipped at 2,000 cells.
- Runs 1–3 hit the default 60 s test timeout on some cases while the machine was loaded (run 1: the
  500-cell per-event run-all; runs 2–3: several 2,000-cell cases). Their completed samples are in
  the table. The file now sets a 10-minute timeout on each size's `describe`; run 4, with that
  change, passed all 39 cases (1 skipped by design).

### M7. Not measured here

- Browser cost of the DOM queries in F2 and F4 (call counts are measured; per-call time in Blink is not).
- Production-build React render time of a cell. M4's milliseconds are jsdom + development React.
- LSP and Copilot end to end (F10): both are disabled in the fixtures.
- Anything with real CodeMirror layout, CSS, or paint: owned by the editor and browser investigators.

## Findings (highest impact first)

### F1. Every kernel event is its own store update, and each update re-reads O(n) selectors

- **Category:** batching, datastructures, algorithms
- **Where:**
  - `frontend/src/core/notebook/replica/replica.ts:417` (`apply`) → `:442` `setStream(reducer.reduce(before, event))` → `:267` `store.set(followedAtom, …)`. One event, one store write; no queue, no `requestAnimationFrame`, no coalescing.
  - Readers that are re-evaluated for every cell on every event:
    `core/executions/atoms.ts:143` (`cellExecutionInputsAtom`, a new object per event) feeding `core/executions/hooks.ts:29` (`useCellExecution`: `selectAtom(…, cellExecutionView, dequal)`, created **twice per cell**: `components/editor/notebook-cell.tsx:393` and `components/editor/cell/cell-context-menu.tsx:59`);
    `atoms.ts:172` (`cellFreshnessAtom`: `freshnessOf` rebuilds its variable index per event) feeding `hooks.ts:50`;
    `atoms.ts:211` (`cellOutputsAtom`: `cellOutputsView` rebuilds a `Map` of every cell's output per event) feeding `atoms.ts:219` (`cellOutputAtom`, `dequal` per cell);
    `core/cells/cells.ts:573` (`cellRuntimeAtom`: three atoms per cell, the first allocating a new object per event).
- **Evidence:** MEASURED. M1: run-all at 500 cells costs 78.7 s per event vs 0.29 s batched (275×), exponent 2.53; one printed line costs 18–24 ms at 500 cells vs 0.09 ms with nothing mounted (M5), so a cell that prints 1,000 lines holds the main thread for tens of seconds; with nothing mounted the same events cost 0.31 s, so the time is selector fan-out, not reducing. M2: 77% inside Jotai's `recomputeInvalidatedAtoms`. Real Chromium (browser investigator): 27.4 s inside the WS handler for smoke-500, 9.85 ms per message, exponent 2.15. M3: only the one affected cell is *notified*, so this work produces no renders.
- **Why it is slow:** all per-cell views derive from four notebook-wide "inputs" atoms that change identity on every event, so Jotai must re-run ~10 selectors per mounted cell (plus `dequal`, `Date` parsing, object allocation) to learn that one cell changed. A 500-cell run is ~2,500 events × ~5,000 selector evaluations.
- **Proposed fix:** two layers, both needed for O(changed).
  1. *Batch.* In `apply`, push stream events and `marimo` notifications onto one ordered queue; flush once per animation frame (`requestAnimationFrame`, with a `setTimeout` fallback when `document.hidden`, since rAF stops in background tabs). A flush reduces each run of stream events with the pure reducer and calls `store.set(followedAtom)` once, then runs the observers (`onExecution`, `onItem`, `onOutput`) and any notification at its original position. Flush synchronously on `ready`, `reset`, and before commands that read confirmed state (`model.flush`, `runCells`). `createHarness(n, "batched")` in the fixture prototypes the reducer and store half of this (it flushes once per delivery, with the console resets and trace updates of a batch folded into one write each) and ends in the same state as the per-event mode.
  2. *Index by cell.* Give each cell its own source of truth so an event invalidates O(1) atoms: e.g. `atomFamily` slices `cellExecutionSliceAtom(id) = selectAtom(executionsAtom, (e) => e.executions.get(e.latest.get(id)))` and `cellResultAtom(id) = selectAtom(resultsAtom, (r) => r.get(id))` (reference equality, no `dequal`), with `cellExecutionView` / freshness / output derived from the slices. Stronger variant: the replica writes per-cell primitive atoms directly and keeps the notebook-wide maps only for imperative `store.get` readers.
- **Expected impact:** batching alone: 78.7 s → 0.29 s in the bench at 500 cells (M1; M6 repeats it: 59–344 s vs 0.20 s); in the browser the 27.4 s of WS-handler time becomes roughly one O(n) flush per frame (a batched single-cell flush measured 39 ms here under load, so ≤ 60 flushes/s is still O(n) each; layer 2 removes that).
- **Effort / risk:** M for batching (ordering of notifications vs stream events, `live` detection in `onItem`, tests that expect synchronous application), M–L for per-cell slices. Risk: stale reads between arrival and flush; code that calls `store.get` right after sending a command.

### F2. `isInVscodeExtension()` walks the whole document on every render of every tooltip/popover/menu wrapper

- **Category:** caching, algorithms
- **Where:** `frontend/src/core/vscode/is-in-vscode.ts:6-9` (`document.querySelector("[data-vscode-theme-kind]")`), called during render at `frontend/src/components/ui/fullscreen.tsx:149` (`withFullScreenAsRoot`) and `:200` (`withSmartCollisionBoundary`). Those HOCs wrap `TooltipPortal`/`TooltipContent` (`components/ui/tooltip.tsx:16,19`), popover, dropdown-menu, context-menu, select, dialog, sheet, toaster.
- **Evidence:** MEASURED counts (M4): 16.4 calls per cell during mount, 8 per single-cell status change, 3 per cell on every sync-status wave (F3). MEASURED in jsdom: memoizing it takes a one-cell status change at 120 cells from 586 ms to 25 ms and the profile attributes 80.5% of that render to this call. INFERRED for Chromium: an attribute selector has no id/class fast path, so an unmatched `querySelector` visits every element; the smoke-500 page has 91,027 elements (browser investigator). A 500-cell load plus first run is roughly 501 × 16.4 + 501 × ~24 ≈ 20,000 such scans. Not timed in a browser.
- **Why it is slow:** an O(DOM) query with a constant answer, executed per component render, makes every cell render O(n) and every notebook-wide render O(n²).
- **Proposed fix:** compute once. `../patches/frontend-state-vscode-detect-once.patch` (lazy module-level memo; `fullscreen.tsx:20` already evaluates it once at import for `MAX_HEIGHT_OFFSET`).
- **Expected impact:** removes ~20,000 full-document scans from a 500-cell load and 8 from every cell status change. If Blink spends 0.3–1 ms per scan of 91k elements this is 6–20 s of the 58 s script time; confirm with a CPU profile filtered on `isInVscodeExtension`.
- **Effort / risk:** S. Assumes the attribute is present before the first render and does not appear later (VS Code sets it on the webview body at load; not verified here). The patch reads it lazily on first call rather than at import to keep that window as wide as possible.

### F3. Every cell re-renders on every document-sync status change

- **Category:** caching (subscription scope), batching
- **Where:** `frontend/src/core/saving/document.ts:21` (`useNotebookDocumentSave` calls `useNotebookDocumentSync()`, which is `useAtomValue(model.syncStatusAtom)` at `core/notebook/document/hooks.tsx:114-118`, only to get `flush`). It is reached from every cell through `useSaveNotebook` (`core/saving/save-component.tsx:104`) at `components/editor/navigation/navigation.ts:204` (`useCellNavigationProps`, in `EditableCellComponent`) and `components/editor/cell/code/cell-editor.tsx:128`. The status is replaced with a fresh object at `core/notebook/document/sync.ts:144,150,166,221`.
- **Evidence:** MEASURED (M4): first keystroke after idle re-renders n of n cells, twice; so does pending → sending 100 ms later. Mocking `useNotebookDocumentSave` (`PROTO=sync`) reduces both to 1 and 0 cells. Each wave also runs `useCellActions()` 20× per cell (F8) and 3 document scans per cell (F2). Wave cost with F2 fixed: 84 / 129 / 381 ms at 30 / 60 / 120 cells in jsdom dev mode (~3 ms per cell; not a browser number).
- **Why it is slow:** a typing burst walks idle → pending → sending → confirming → idle (4 status objects), and continuous typing adds sending → confirming per round trip; each is a full-notebook render of the heaviest component in the app.
- **Proposed fix:** `../patches/frontend-state-save-without-sync-subscription.patch`: add `useNotebookDocumentFlush()` returning the model's stable `flush`, and use it in `useNotebookDocumentSave`. Also worth doing: keep one status object per state in `sync.ts` (`store.set(statusAtom, IDLE)`) so equal states do not notify, and hoist `useSaveNotebook` out of per-cell hooks (a single notebook-level handler for `global.save`).
- **Expected impact:** 4+ full-notebook render waves per typing burst → 0. At 500 cells that is 2,000+ `EditableCell` renders per burst removed.
- **Effort / risk:** S. `SaveComponent` still needs the status (through `needsSaveAtom`), which is unaffected.

### F4. The floating outline re-queries the document for every heading, twice per markdown cell run

- **Category:** algorithms, caching, dom-listeners
- **Where:**
  - `frontend/src/components/editor/chrome/panels/outline/floating-outline.tsx:15-18`: `findOutlineElements(items)` runs in render. It calls `findOutlineItem` (`useActiveOutline.tsx:153-173`), which does `document.querySelectorAll('[id="…"]')` per heading (`:160`) or `document.evaluate` (`:165`).
  - `useActiveOutline.tsx:36-97`: the effect depends on the array created in render, so every render disconnects and rebuilds the `IntersectionObserver` and runs an O(h²) `map().filter().indexOf()` over the headings (`:78-85`).
  - `frontend/src/core/cells/cells.ts:491` (`notebookOutline`) returns a new object whenever any `cellOutlineAtom` does; `core/executions/atoms.ts:228` re-parses whenever `cellOutputAtom` changes; `core/executions/output.ts:86` puts `timestamp: endedAt(record)` in the output, which is `started_at` while running and `completed_at` after.
- **Evidence:** MEASURED (M3, M4): re-running one markdown cell with byte-identical HTML notifies `cellOutputAtom`, `cellOutlineAtom` and `notebookOutline` twice (on `output`, again on `completed`), and `FloatingOutline` renders twice with h `querySelectorAll` calls each (120 calls for 60 headings). INFERRED for the 521-cell notebook (269 markdown cells, ~269 headings): a run-all is up to 2 × 269 renders × 269 queries ≈ 145,000 attribute-selector scans of a 91k-element document, plus 538 `IntersectionObserver` rebuilds over 269 targets and 538 re-renders of `OutlineList` + `MiniMap`. React may merge renders that land in the same frame; the scans per render do not shrink.
- **Why it is slow:** an O(h) × O(DOM) query in render, re-triggered by a field (`timestamp`) that has nothing to do with headings.
- **Proposed fix:** (a) make outlines value-stable: derive `cellOutlineAtom` from the output's `mimetype` + `data` only (e.g. `selectAtom(cellOutputAtom(id), (o) => o && { mimetype: o.mimetype, data: o.data }, shallow)` then parse), and wrap `notebookOutline` in `createDeepEqualAtom`; (b) in `FloatingOutline`, `useMemo` the element lookup on `items` and resolve all headings with one pass (`document.querySelectorAll("h1,h2,h3,h4,h5,h6")` into a `Map<id, Element[]>`), or use `getElementById` for the first occurrence; (c) keep one `IntersectionObserver` and diff targets; (d) do not change `timestamp` between the running and completed views of the same output.
- **Expected impact:** identical re-runs: 2 outline renders and 2h scans per markdown cell → 0. Changed headings: h scans → 1.
- **Effort / risk:** S–M. Duplicate heading ids and id-less headings (XPath) must keep their current occurrence semantics; `OutlinePlugin` and the outline panel read the same atom.

### F5. A keystroke is O(n) in the store and re-renders the cell column

- **Category:** datastructures, algorithms, caching
- **Where:**
  - `frontend/src/core/notebook/document/state.ts:169` (`documentAtom` → `viewDocument`, `draft.ts:403`: rebuilds a `Map` of every cell, a `Set` of the order, and filters all keys) and `state.ts:174` (`changesAtom` → `toChanges`, `draft.ts:443`: calls `viewDocument` again, plus `new Set(order)` and `sameOrder`), both per keystroke. These are the cheap part (M6: 0.03–0.04 ms at 500).
  - `frontend/src/core/cells/document.ts:128` (`followDocument`) → `:63` (`applyDocument`: `dequal` of the whole order at `:68`, `dequal` of every cell's config at `:38`) → new `cellData` record → `notebookAtom` changes → every `get(notebookAtom)…[cellId]` atom re-reads (`cells.ts:569`, `:573`, `:586`: 3n) plus `cellErrorsAtom` (`:443`), `runReasonAtom` (`:433`), `cellIdToNamesMap` (`:497`).
  - `frontend/src/core/cells/layout.ts:144` (`layoutAtom`): a new `Layout` object per document change. `components/editor/renderers/cell-array.tsx:48,103,174` read it, and `:204` passes `items={[...column.visible]}` to `SortableContext`.
- **Evidence:** MEASURED. M1: 12.7 ms per keystroke at 500 mounted (exponent 1.43) vs 0.56 ms with nothing mounted; M6: 9.6–47 ms at 500 and 39–89 ms at 2,000. Profile: 85% in `reconcileDocument`'s fan-out. M3: `layoutAtom` and `cellErrorsAtom` notify on every keystroke. M4: a `useLayout()` reader re-renders on every keystroke, and a `SortableContext` given a fresh array of the same ids re-renders all n `SortableCell`s (n of n; their children do not re-render).
- **Why it is slow:** one character changes one cell's code, but the draft view, the change list, the follower record, and the layout are all rebuilt from scratch, and three per-cell atoms hang off one monolithic `notebookAtom`.
- **Proposed fix:** (a) finish MO-8349 for code: components already can read code/name/config with `useNotebookCellCode`/`selectCellField`; stop copying code into `notebookAtom.cellData` so a keystroke never touches `notebookAtom`. Until then split `notebookAtom` into `cellIdsAtom` + per-cell `atomFamily` primitives (`cellData`, `cellRuntime`) + a non-reactive `Map` of handles. (b) Replace the `Record<CellId, …>` maps in `NotebookState` with `Map`s or per-cell atoms: `{ ...cellData, [id]: next }` is 0.3 ms at 500 keys but 2.1 ms at 2,000 (M6 `applyDocument`), where V8 drops the record to dictionary mode. Optionally make `viewDocument` incremental and let `toChanges` reuse the view. (c) Build `layoutAtom` from `selectOrder(documentAtom)` and a `selectAtom` of column configs so it is identity-stable across code edits; memoize the `items` array on `column.visible` so `SortableContext` sees a new array only when the visible cells change.
- **Expected impact:** keystroke store cost O(n) → O(1): the 12.7 ms mounted figure at 500 falls to the 0.56 ms unmounted figure once nothing per-cell hangs off `notebookAtom`; per-keystroke React work drops from `CellArray` + `CellColumn` + n × (`SortableCell`, `SortableCellInternal`, `CellDragHandle`) to the edited cell.
- **Effort / risk:** (c) S; (b) S–M; (a) M–L (touches every reader of `cellData`). Risk: fold/column logic depends on layout recomputing when a cell's `column` config changes.

### F6. A confirmed edit is a second O(n) wave, once per edit round trip

- **Category:** algorithms, caching
- **Where:** `frontend/src/core/notebook/replica/resources/document.ts:67-76` (`cell`: copies the whole cell `Map`) and `:46-58` (`publish`: `new Set(order)`, two O(n) scans); the new `Document` then invalidates `cellExecutionInputsAtom`, `cellFreshnessAtom`, `cellOutputInputsAtom` (`core/executions/atoms.ts:143,156,193`: all take `document.cells`) and every `cellRuntimeAtom` (`cells.ts:576` reads `confirmedDocumentAtom`), i.e. the full F1 fan-out; the `analysis` event replaces the whole analysis (`resources/analysis.ts:8`) and re-runs `blockedDescendants` (`atoms.ts:130`).
- **Evidence:** MEASURED (M3): one confirmation notifies `cellExecutionInputsAtom` twice, the freshness/output inputs, `layoutAtom`, `runReasonAtom`, `syncStatusAtom` twice, and only one cell's atoms. M6 "one confirmed edit": 122 ms (35–149) at 500 cells and 305 ms at 2,000 for the three events, on every confirmation (one per edit round trip while typing; the first waits 100 ms). The `analysis` payload is 36.6 KB at 500 cells per confirmation (browser investigator's `event:analysis`).
- **Why it is slow:** per-cell execution/output/freshness views take the *entire* confirmed cell map as an input, so changing one cell's fingerprint re-evaluates them for all cells.
- **Proposed fix:** same per-cell slicing as F1 (views read `document.cells.get(id)`, which is reference-stable for untouched cells); batch the `cell` + `document` + `analysis` triple into one store update (F1 layer 1 does this).
- **Expected impact:** O(n) → O(1) selectors per confirmation; one store update instead of three.
- **Effort / risk:** comes with F1.

### F7. O(n) and O(n²) helpers inside the per-event path

- **Category:** algorithms, datastructures
- **Where / evidence (MEASURED in M5 unless noted):**
  - `frontend/src/core/executions/select.ts:143-164` (`awaited`): `run.origin.cell_ids.includes(id)` for every unplanned cell. For a user "run all" (`origin.kind === "cells"`), `cellExecutionView` × n costs 3.3 ms at 500 and 36.5 ms at 2,000 during the queue phase, per event, per view (two views per cell), for n queue events. Fix: precompute `Set`s of awaited cell ids per run once per inputs object (`WeakMap<Executions, Set>`), or carry `requested`/awaited as a `Set` in `cellExecutionInputsAtom`.
  - `select.ts:63-64,173-186`: `Time.parse` up to 4× per cell per event (0.32 ms per event at 500). Fix: parse in the reducer when the record arrives, or memoize per record in a `WeakMap`.
  - `frontend/src/core/cells/runs.ts:84,102` (`addExecution`): copies the run's `cellRuns` map and the `runMap` on every lifecycle change: 42.7 ms per run-all at 500, 1,057 ms at 2,000 (exponent 2.3). Fix: mutate a per-run `Map` behind a version counter, or apply a batch in one copy.
  - `frontend/src/core/cells/execution-console.ts:91` → `cells.ts:171,379-400` (`startCellConsole`): every `running` event writes `notebookAtom`, which re-reads all 3n per-cell atoms and the notebook-wide selectors a second time (8.2% of the run-all profile; M3 shows `notebookAtom` and `cellErrorsAtom` notifying on `running`). Fix: move `cellRuntime` into a per-cell `atomFamily` so the reset writes one atom, and fold the resets of a batch into one write (the bench's batched mode does this).
  - `frontend/src/core/cells/execution-console.ts:109` → `cells.ts:248-253` (`addLogs`): every live stdout/stderr item copies the unbounded `cellLogs` array and writes `notebookAtom`, a second full fan-out per printed line (+5.6 ms per line at 500 cells, M5). Fix: keep logs in their own atom (only the logs panel reads them, `components/editor/chrome/panels/logs-panel.tsx:23`), append in place behind a version counter, and cap the length.
  - `frontend/src/core/notebook/replica/resources/executions.ts:119-130` (`set`), `:150-169` (`attach`), `results.ts:46` (`retainResult`): each event copies the `executions`, `latest`, and `results` maps, and each console line copies its execution's `items` map (O(m²) for a cell that prints m lines). Pure reducer: 125 ms per run-all at 500, exponent 2.22 (M1); 1.9–8.6 s at 2,000, half or more of the *batched* run-all in each run (M6). Fix: when batching, reduce a batch against one mutable draft and freeze once.
  - `executions.ts:207-212` (`sameShown`): two `JSON.stringify` of the output on every `execution` and `output` event: 3.6 ms per event for a 1 MB output (three events per run). Fix: compare `output` by reference first, then by id/length.
  - `select.ts:207-211` (`unfinished`): spreads every execution into an array for `anyRunning`, `queuedOrRunningCount`, `onlyScratchRunning`, `scratchStatus`, `runningCellIds`, each per event. INFERRED small; fix with a count maintained by the reducer.
  - `frontend/src/core/dom/uiregistry.ts:132-140` (`removeElementsByCell`): scans every registered UI element id per `remove-ui-elements` message (one per code cell per run). INFERRED small for the smoke shape (no UI elements); quadratic for `outputs-N`.
- **Why it is slow:** each is linear in n and runs once per event, so each is quadratic per run.
- **Expected impact:** after F1, these are what remains of a run-all (the 286 ms batched figure includes the 125 ms pure reducer, ~43 ms of `addExecution`, and one jsdom `DOMParser` call per markdown output).
- **Effort / risk:** S each.

### F8. Each cell does a lot of eager, repeated work per render

- **Category:** lazy-init, caching
- **Where / evidence:**
  - MEASURED (M4): every cell renders 5 times while mounting.
  - MEASURED (M4): `useCellActions()` (`frontend/src/core/cells/actions.ts:654-733`: 33 `useSetAtom` + `useReducerActions` + `useMemo`) is called 73.8 times per cell during mount and 20–25 times per cell re-render. Call sites per render include `notebook-cell.tsx:402,835`, `navigation.ts:207,208`, `cell-editor.tsx:134`, `CreateCellButton.tsx:36` (×2 per cell), `useCellActionButton.tsx:99` (×2), `useDeleteCell.tsx:12,43`, `useSplitCell.tsx:12`, `useAnswerPrompt.ts:13`. At 500 cells that is ~37,000 calls (~1.2 M hook invocations) to obtain one object that is stable for the store's lifetime.
  - `components/editor/cell/cell-context-menu.tsx:57-73` and `components/editor/cell/cell-actions.tsx:66` each call `useCellActionButtons` (`components/editor/actions/useCellActionButton.tsx:91`) on every cell render, building the full action list (icons, labels, closures) for two menus that are closed. The context menu additionally subscribes to cell data, runtime, execution, and output only to build that list (`cell-context-menu.tsx:57-60`), which is the second `useCellExecution` selector per cell in F1. INFERRED cost; MEASURED that they run (the `useCellActions` counts above).
  - `notebook-cell.tsx:628` and `:1078`: a `TooltipProvider` per cell. `:494`: a `ResizeObserver` per markdown cell (`skip: !isMarkdown`) whose callback sets cell state. `cell-editor.tsx:433`: an `IntersectionObserver` per editor. `Output.tsx:444`, `output/console/ConsoleOutput.tsx:127`: a `ResizeObserver` per rendered output and per non-empty console (`hooks/useOverflowDetection.ts:25`). `ConsoleOutput` mounts for every cell, including those with no console output (`notebook-cell.tsx:751`).
  - No windowing: `cell-array.tsx:223-243` maps every visible cell to a mounted `Cell`; there is no `content-visibility`, `react-virtual`, or equivalent in the notebook tree (grep: only select lists, data tables, slides).
- **Why it is slow:** per-cell constants multiply by 500 at mount and again on every notebook-wide render (F3, layout changes, config changes).
- **Proposed fix:** (a) make actions a module-level singleton per store (`getCellActions(store)` cached in a `WeakMap`, or a context value created once in `CellArray`) so `useCellActions()` is one `useContext`; (b) build action lists lazily: render `ContextMenuContent`/`PopoverContent` children from a component that calls `useCellActionButtons` only when open (Radix mounts content on open), and let it read cell state with `store.get` at open time; (c) one `TooltipProvider` for the notebook; (d) share one `ResizeObserver`/`IntersectionObserver` across cells; (e) mount `ConsoleOutput` only when there are rows or a pending prompt.
- **Windowing, and what makes it hard:** `content-visibility: auto` with `contain-intrinsic-size` on `.marimo-cell` is the low-risk step (keeps DOM, so find-in-page, anchors, `scrollIntoView`, print all still work; ask the CSS investigator for layout cost). True virtualization would have to preserve: (1) imperative handles (`cellHandles[id].current.editorView`, used by `getAllEditorViews`, find/replace, `foldAll`, `formatAll`, LSP `getNotebookEditors`, delete/undo's `serializedEditorState`); (2) `focusAndScrollCellIntoView` and `scrollKey` after create/move; (3) outline anchors (`findOutlineItem`) and the `IntersectionObserver`-based active heading; (4) dnd-kit's `SortableContext` (`cell-array.tsx:202`), whose sorting strategy works from the rects of the registered items; (5) output DOM that must survive (iframes, anywidgets, UI element state; `notebook-cell.tsx:304-305,662-665` keep trees mounted on purpose across edit ↔ present); (6) browser find-in-page and print/export, which read the DOM. A staged approach: keep outputs mounted, virtualize only the editor chrome + CodeMirror view for off-screen cells (the progressive `editorMountScheduler` already defers builds and `ensureCellEditorView` promotes on demand).
- **Expected impact:** (a) removes ~1.2 M hook calls at mount for 500 cells; (b) halves per-cell execution selectors and removes two menu builds per cell render.
- **Effort / risk:** (a) S; (b), (c), (e) S–M; windowing L.

### F9. Notebook-chrome components that render on every event

- **Category:** caching (subscription scope)
- **Where / evidence (INFERRED from the subscriptions; M3 shows the atoms notify on every event):**
  - `frontend/src/core/export/hooks.ts:125` (`useEnrichCellOutputs`: `useAtomValue(cellOutputsAtom)`), used by `useAutoExport` in `SaveComponent` (`core/saving/save-component.tsx:60`): the save button re-renders on every `execution`/`output` event (~2,500 per run-all at 500). Fix: read with `store.get` inside the returned callback.
  - `frontend/src/components/editor/header/status.tsx:81` and `components/scratchpad/scratchpad.tsx:76`: `useAtomValue(cellExecutionInputsAtom).executions`. Fix: `selectAtom` to the boolean/status they display.
  - `frontend/src/components/editor/cell/collapse.tsx:68-69` (`CollapsedCellBanner`): reads both notebook-wide inputs atoms; each collapsed section re-renders per event and runs `getDescendantsStatus` over its fold. Fix: a per-fold selector with `dequal`.
  - `frontend/src/core/cells/cells.ts:443` (`cellErrorsAtom`): depends on `notebookAtom`, so it rebuilds (0.63 ms at 500, M5) and returns a new array on every keystroke and every `running` event; `useCellErrors` readers (error panel) re-render. Fix: depend on `cellIdsAtom` and a names selector; wrap in `createDeepEqualAtom` or compare by error identity.
  - `frontend/src/components/editor/chrome/panels/dependency-graph-panel.tsx:17` (`useCellDataAtoms`, `cells.ts:561-565`): `selectAtom` returning a new array per `notebookAtom` change; when the panel is open it re-renders per keystroke.
- **Expected impact:** small each; they are the remaining per-event renders once F1–F4 are fixed.
- **Effort / risk:** S each.

### F10. LSP and Copilot rebuild and resend the whole notebook per change (when enabled)

- **Category:** streaming, algorithms
- **Where:** `frontend/src/core/codemirror/lsp/notebook-lsp.ts:343-360` (`getNotebookCode`: `getEditorCodeAsPython` for every cell), `:445-463` (`sync`: `createNotebookLens` merges every cell and sends `contentChanges: [{ text: lens.mergedText }]`), called from `textDocumentDidChange` (`:466-473`) and before every hover/completion/definition request. `frontend/src/core/codemirror/copilot/getCodes.ts:12-27,29-53` (`notebookCellCodes`, `getCodes`) and `copilot/language-server.ts:312,331` do the same for Copilot.
- **Evidence:** MEASURED (M5): merging is cheap (0.41 ms at 500) but the `didChange` payload is 426 KB at 500 cells and 1.7 MB at 2,000, per change. INFERRED: the per-cell `getEditorCodeAsPython` (500 `doc.toString()` + language-adapter transforms) and the server-side reparse were not timed (pylsp/copilot are off in the fixtures; the editor investigator owns `core/codemirror/**`).
- **Why it is slow:** full-document sync of a virtual file that grows with the notebook.
- **Proposed fix:** cache each cell's Python text keyed by its `EditorState.doc` identity; send incremental `contentChanges` with the changed cell's line range (the lens already knows each cell's line offset); debounce `didChange`.
- **Expected impact:** 426 KB → the edited lines per change.
- **Effort / risk:** M. Servers that only declare full sync need the current path as a fallback.

## Ruled out

- **Protocol validation (zod) per event:** 24 ms for a 2,508-event run-all at 500 cells, linear (M1). ~10 µs per event.
- **Snapshot reducer at load:** O(n²) map copies (`resources/document.ts:67-76`, `resources/executions.ts:289-292`) but 12 ms at 500 in M1 (8–120 ms across the M6 runs) and ~230 ms at 2,000; browser: 501 `cell` events took 53–72 ms in total.
- **React render fan-out for kernel events:** one cell's status/output change re-renders exactly that cell (M4), because every per-cell hook uses `selectAtom` with equality. The problem is recomputation (F1), F2, and F4, not render fan-out.
- **Dirty tracking:** `needsSaveAtom` (`core/saving/state.ts:32-56`) compares two etags and the sync status. No per-keystroke serialization or code comparison. `useAutoSave` (`core/saving/useAutoSave.ts`) is a timer keyed on the document version.
- **Local/session storage:** no notebook-sized writes; `atomWithStorage` users hold UI preferences only (panel state, AI settings, wrap-text). WASM saving (`core/wasm/store.ts`) is outside the edit server path.
- **`startCellConsole`'s record copy itself:** 1 µs at 500 keys (0.62 ms at 2,000, where V8 leaves fast mode). The cost is the `notebookAtom` fan-out it triggers (F7).
- **`notebookOutline` read with cached outlines:** 0.3 µs. The cost is in what re-triggers it (F4).
- **`createNotebookLens`:** 0.41 ms at 500 (F10 is about payload size).
- **`document.title` / favicon:** `core/edit-app.tsx:92-98` depends on filename and app title only; `dynamic-favicon.tsx:72` reads `cellErrorCount` (a number, stable).
- **`variables` notification fan-out:** one message per run, not per cell (wire trace); `remove-ui-elements` is one per code cell but does no store write.

## Benchmarks added

- `frontend/benchmarks/large-notebook-state.bench.ts`: 500 and 2,000 cells. Load (validation, reducer), typing (keystroke, confirmed edit, and `viewDocument`/`toChanges`/`applyDocument` separately), kernel events (one cell and every cell, per-event vs batched prototype, reducer only), selectors, and create/delete/move at the top.
- `frontend/benchmarks/large-notebook-state.fixture.ts`: the event stream, the mounted-cell subscriptions, and `createHarness(n, "per-event" | "batched")`.

```sh
cd frontend
pnpm exec vitest bench benchmarks/large-notebook-state.bench.ts \
  --mode test --run --no-file-parallelism \
  --reporter=json --outputFile ../.context/large-notebook-state.json
```

The per-event "every cell runs" case is skipped at 2,000 cells (quadratic; minutes per sample).
Both files pass `pnpm exec tsgo --noEmit -p .`, `oxfmt`, and `oxlint` (only the `expect-expect`
warnings the existing benches also have).

Scratch (not for commit), in `.context/perf/frontend-state/`: `probe.test.ts` (M1), `profile.test.ts`
and `cell-event.test.tsx` (M2, CPU profiles), `fanout.test.ts` (M3), `renders.test.tsx` (M4, with the
two prototypes behind `PROTO=`), `micro.test.ts` and `console.test.ts` (M5), `fill_report.py` (M6 table from `bench-run*.json`), `vitest.config.ts`. `renders.test.tsx` is a
candidate regression test ("a kernel event re-renders one cell", "a keystroke does not re-render
other cells") once F2/F3 land; today its assertions would encode the bugs.

Proposed diffs: `../patches/frontend-state-vscode-detect-once.patch`,
`../patches/frontend-state-save-without-sync-subscription.patch` (both `git apply --check` clean).
