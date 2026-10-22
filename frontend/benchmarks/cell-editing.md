# Cell editing benchmarks

Measure before changing production code. Use 25 and 100 cells for browser measurements. Use 1,000 cells for scaling tests.

## Instructions

Run each revision three times on an idle machine. Keep the fixture, browser, CPU slowdown, and typing length constant.
Save each run to a separate output path.

### Microbenchmarks

From the repository root:

```sh
mkdir -p .context
cd frontend
pnpm exec vitest bench benchmarks/cell-editing.bench.ts benchmarks/cell-analysis.bench.ts \
  --mode test --run --no-file-parallelism \
  --reporter=json --outputFile ../.context/cell-editing-baseline.json
```

For comparisons, save each revision to a separate file and compare the per-test `benchmarks` results in the JSON reports. Vitest 5 removed `--compare` and changed the report format; regenerate baselines recorded with Vitest 4.

- `cell-editing.bench.ts`: reducer, document conversion, and Jotai subscriptions at 10, 25, 100, and 1,000 cells.
- `cell-analysis.bench.ts`: Python transactions and analyzers at 20, 200, and 2,000 lines, with 1,000 known variables.

These benchmarks exclude React, DOM layout, and network work.

### Browser benchmark

From `frontend`, build the production editor and create disposable fixtures:

```sh
pnpm build
cp -R dist/. ../marimo/_static/
node benchmarks/create-editing-fixtures.ts ../.context/browser-fixtures
cd ../.context/browser-fixtures
uv run --no-project --with-editable ../.. marimo edit . \
  --headless --no-token --skip-update-check --port 29871
```

The fixture directory must not exist. Fixtures contain 20 editable lines per cell, excluding the generated return statement.
Copilot and pylsp are disabled. Default fixtures have no outputs.
Add `--outlines` to create `outline-25.py` and `outline-100.py` with 48 and 198 rendered headings.
The harness restores edits after successful runs. Failed or interrupted runs can leave edits behind.

In another terminal, from `frontend`:

```sh
node benchmarks/cell-editing.browser.ts \
  'http://127.0.0.1:29871/?file=browser-25.py' ../.context/browser-results
node benchmarks/cell-editing.browser.ts \
  'http://127.0.0.1:29871/?file=browser-100.py' ../.context/browser-results
```

For fixtures generated with `--outlines`, use these commands instead:

```sh
EDITING_BENCH_HEADINGS=48 node benchmarks/cell-editing.browser.ts \
  'http://127.0.0.1:29871/?file=outline-25.py' ../.context/outline-results
EDITING_BENCH_HEADINGS=198 node benchmarks/cell-editing.browser.ts \
  'http://127.0.0.1:29871/?file=outline-100.py' ../.context/outline-results
```

| Environment variable | Default | Purpose |
| --- | --- | --- |
| `EDITING_BENCH_RUNS` | `3` | Repetitions |
| `EDITING_BENCH_RATES` | `1,4,6` | CPU slowdown rates |
| `EDITING_BENCH_CONTINUOUS_KEYS` | `30` | Characters at 80 ms intervals, followed by 20 characters at 400 ms intervals |
| `EDITING_BENCH_HEADINGS` | Unset | Wait for this number of rendered headings before typing |
| `EDITING_BENCH_PROFILE` | `0` | Set to `1` for a CPU profile and browser trace |
| `EDITING_BENCH_REACT` | `0` | Set to `1` for React commit records with the profiling build |

Input duration spans `beforeinput` capture through `input` bubbling. Frame duration spans keydown capture through the next animation frame.
Neither includes initial input queuing or measures keyboard-to-paint latency. JSON also includes long tasks and thresholded Event Timing entries.

### Profiling

For React records, check the recorder and build with profiling enabled:

```sh
node benchmarks/check-react-commits.ts
pnpm exec vite build --config vite.editing-profile.mts
cp -R dist/. ../marimo/_static/
EDITING_BENCH_RUNS=1 EDITING_BENCH_RATES=6 EDITING_BENCH_REACT=1 \
  node benchmarks/cell-editing.browser.ts \
  'http://127.0.0.1:29871/?file=browser-25.py' ../.context/react-results
```

Recheck the recorder after React upgrades because it uses private DevTools interfaces.
For CPU profiles, set `EDITING_BENCH_PROFILE=1` and open the `.cpuprofile` or `.trace.json` in Chrome DevTools.
For source maps, build with `pnpm exec vite build --sourcemap hidden` and copy `dist/.` again.
Use the normal production build for latency comparisons. Profiling adds overhead.

## Benchmarks

### Browser input processing

*Last recorded: 2026-10-20 · Apple M4 Max · Chromium 153.0.8010.12 · 6× CPU slowdown*

Milliseconds, median of three per-run percentiles. Paused typing uses 20 characters after the continuous burst.

| Cells | Continuous characters | Continuous p50 | Continuous p95 | Paused p50 | Paused p95 |
| --- | --- | --- | --- | --- | --- |
| 25 | 30 | 13.0 | 18.6 | 11.4 | 13.6 |
| 25 | 150 | 10.8 | 14.1 | 11.0 | 13.5 |
| 100 | 30 | 17.3 | 19.2 | 16.7 | 19.4 |

### Input processing with rendered headings

*Last recorded: 2026-10-20 · Apple M4 Max · Chromium 153.0.8010.12 · 6× CPU slowdown · background CPU load present*

Milliseconds, median of three per-run p95 values; 30 continuous and 20 paused characters.
Before/after narrowing outline subscriptions to cell order and runtime state.

| Cells | Headings | Continuous before | Continuous after | Paused before | Paused after |
| --- | --- | --- | --- | --- | --- |
| 25 | 48 | 24.5 | 18.0 | 25.7 | 16.0 |
| 100 | 198 | 74.9 | 24.5 | 38.9 | 23.6 |

The 100-cell continuous p95 ranged from 37.2–110.7 ms before and 22.8–24.9 ms after.

### Favicon input processing

*Last recorded: 2026-10-20 · Apple M4 Max · Chromium 153.0.8010.12 · 6× CPU slowdown · background CPU load present*

Milliseconds, median of three per-run p95 values; no outputs, 150 continuous and 20 paused characters.
Before/after narrowing favicon subscriptions and fixing reset cleanup.

| Cells | Continuous before | Continuous after | Paused before | Paused after |
| --- | --- | --- | --- | --- |
| 25 | 12.9 | 13.2 | 12.4 | 12.2 |
| 100 | 19.7 | 19.5 | 20.5 | 20.6 |

For 50 keystrokes at 25 cells, favicon renders and icon lookups each fell from 50 to 0.

### Isolated operations

*Last recorded: 2026-10-19 · Apple M4 Max · Node 24.22.0 · Vitest 4.1.11 · jsdom*

Milliseconds, median of three run means. Store measurements use synthetic subscriptions and development Jotai.

| Operation | Size | Mean, ms |
| --- | --- | --- |
| Reducer and document conversion | 1,000 cells | 0.0011 |
| Store with cell subscribers | 100 cells | 0.283 |
| Store with cell subscribers | 1,000 cells | 3.525 |
| Store with cell and derived subscribers | 1,000 cells | 4.599 |
| Python state transaction | 2,000 lines | 0.630 |
| Reactive-reference analysis | 2,000 lines | 5.739 |
| Code-lens declaration analysis | 2,000 lines | 0.807 |
| Document serialization | 2,000 lines | 0.0166 |
