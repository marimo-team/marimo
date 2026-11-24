# Server and wire protocol — large-notebook performance

Scope: HTTP + WebSocket traffic between `marimo edit` and the browser, and the
server's per-message work, for `smoke-N` / `outputs-N` at 100 / 500 / 2000 cells.
No browser was used: a Python client (`websockets` + `http.client`) performs
the frontend's handshake and requests.

**Read this first — the protocol is not what the task brief assumed.** The
editor now speaks the *host protocol* (`marimo/_core/`, `marimo/_server/host/`):

- `kernel-ready` is 455 bytes. Code, names and configs arrive as one `cell`
  record per cell, the order as a `document` record, dependencies as an
  `analysis` record.
- The legacy `cell-op` notification is no longer forwarded to the editor
  (`marimo/_server/host/events.py:132`). Each run is published as `run` /
  `execution` / `output` / `console` / `variable` records.
- `/api/kernel/save`, `/run`, `/instantiate`, `/sync/cell_ids` no longer exist.
  The editor sends per-cell deltas (`POST /api/marimo/v1/notebooks/{id}/edits`),
  `POST .../save` with an empty body, and `POST .../runtime/runs` with cell ids.

So "full-notebook save payloads" and "giant kernel-ready" are gone from the
wire. The O(notebook) work moved to the **server side of each edit and save**
(F1, F4, F5).

## Measurements

Environment: Apple M4 Max, Python 3.13.9, uvicorn 0.54.0, websockets 17.4,
msgspec 0.22.0. **The machine was heavily oversubscribed for the whole session
(1-minute load average 30–240 on 14 cores)**, so:

- byte and frame counts are exact and reproducible;
- **CPU** numbers are `time.thread_time()` / `time.process_time()` (robust to
  load, still somewhat inflated by cache contention);
- wall-clock numbers are labelled "wall" and are upper bounds. Rely on ratios
  and scaling, not absolutes.

All scripts are in `.context/perf/wire-protocol/` (see "Benchmarks added").

### M1. Page bootstrap over HTTP

`curl -D - -H 'Accept-Encoding: gzip, deflate, br, zstd'`, and `assets.py`
over `marimo/_static`.

| Resource | Bytes | content-encoding | cache-control | Validators |
| --- | --- | --- | --- | --- |
| `/` (index.html), any notebook size | 25,015 (template 14,891 + config) | none | `private, no-cache` | sha256 `etag`, 304 works |
| `/assets/index-*.js` (entry) | 719,857 | none | **none** | `etag`, `last-modified` |
| `/assets/index-*.css` | 389,125 | none | **none** | `etag`, `last-modified` |

The notebook is **not** inlined in the HTML (`"notebook": null`); size is
constant at 100/500/2000 cells.

| Eager set referenced by index.html | Files | Raw bytes | gzip -6 | brotli -5 |
| --- | --- | --- | --- | --- |
| entry `<script type=module>` | 1 | 719,857 | 222,672 | 204,017 |
| `modulepreload` | 131 | 3,689,242 | 1,199,122 | 1,129,538 |
| stylesheets | 4 | 401,836 | 63,503 | 56,321 |
| **JS + CSS total** | **136** | **4,810,935** | **1,485,297** | **1,389,876** |
| fonts/images `preload` | 8 | 922,341 | (already compressed) | |

Largest eager chunks: `cells-*.js` 1,050 KB, `index-*.js` 720 KB,
`JsonOutput-*.js` 527 KB, `chunk-7TTQLYRW-*.js` 493 KB, `index-*.css` 389 KB,
`dist-9uo8aAYM.js` 343 KB, `fullscreen-*.js` 165 KB. Largest lazy chunks:
`Plot-*.js` 4.65 MB, `node-sql-parser-*.js` 2.43 MB, `react-vega-*.js` 744 KB,
`edit-page-*.js` 465 KB, `terminal-*.js` 449 KB. Total JS/CSS in the build:
441 files, 21.2 MB.

Revalidating the 136 eager files with `If-None-Match` over one keep-alive
connection: 136 × `304` in 399 ms wall (2.9 ms each, each through the full
middleware stack).

There is no compression middleware anywhere in the HTTP stack
(`marimo/_server/main.py:70-131`; `grep -ri 'gzip|compress|brotli' marimo/_server`
finds nothing). JSON API responses are uncompressed too (`content-encoding`
absent on every `/api/...` response measured).

### M2. WebSocket first connect + run-all (auto_instantiate on)

`matrix.py` → `scripts/benchmarks/ws_traffic.py`; a fresh server per run; 3
runs; counts identical across runs. "Wire" is bytes read from the socket
(`permessage-deflate` on, as a browser negotiates).

| Fixture | Cells | Frames | Frames/cell | JSON bytes | Bytes/cell | Wire bytes | Wire % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| smoke-100 | 101 | 581 | 5.75 | 315,550 | 3,124 | 50,565 | 16.0% |
| smoke-500 | 501 | 2,781 | 5.55 | 1,567,720 | 3,129 | 245,001 | 15.6% |
| smoke-2000 | 2,001 | 11,031 | 5.51 | 6,333,381 | 3,165 | 973,465 | 15.4% |
| outputs-100 | 101 | 587 | 5.81 | 345,884 | 3,425 | 61,302 | 17.7% |
| outputs-500 | 501 | 2,812 | 5.61 | 1,722,967 | 3,439 | 299,529 | 17.4% |
| outputs-2000 | 2,001 | 11,156 | 5.58 | 6,958,435 | 3,477 | 1,199,196 | 17.2% |

Scaling exponent, 100 → 2000 cells: bytes 1.00, frames 0.99. **Traffic is
linear in cell count; there is no O(n²) in bytes.** Nothing is re-sent per
cell during the first run (`variables` is sent once per run).

Per kind, smoke-500 (`analyze_trace.py trace-smoke-500.jsonl`):

| Kind | Frames | Bytes | Share | Avg | Notes |
| --- | --- | --- | --- | --- | --- |
| `cell` (snapshot) | 501 | 526,959 | 33.6% | 1,052 | 69% is source; 323 B/cell is envelope (`code_fingerprint` 101 B, `config` 81 B, `notebook_id` 36 B …) |
| `execution` completed | 501 | 325,205 | 20.7% | 649 | full record again |
| `execution` running | 501 | 241,361 | 15.4% | 482 | full record again |
| `execution` queued | 501 | 219,316 | 14.0% | 438 | |
| `output` | 501 | 182,266 | 11.6% | 364 | 251 of them are `media: null` |
| `analysis` | 1 | 37,515 | 2.4% | | 75 B/cell |
| `marimo:remove-ui-elements` | 251 | 20,332 | 1.3% | 81 | one per code cell |
| `marimo:variables` | 1 | 3,777 | 0.2% | | 7.5 B/cell (star graph `used_by`) |
| `document` | 1 | 3,767 | 0.2% | | 7.5 B/cell (`order`) |
| `marimo:kernel-ready` | 1 | 455 | 0.0% | | layout, app_config, capabilities, ids |
| everything else | 22 | 6,767 | 0.4% | | run ×3, variable ×8, notebook, runtime, attachment, ready … |

Messages per cell: 1 `cell` + `execution` ×3 (queued, running, completed) + 1
`output` + 0.5 `remove-ui-elements` = 5.5 frames. The kernel sends the server
6.0 messages per cell (3,012 at 500 cells, 1,206,201 bytes): `execution` ×3 +
`cell-op` ×2.5 + `remove-ui-elements` ×0.5.

Timeline, ms since WebSocket connect, median of 3 (`matrix.py`, wall, load
average 30–45 — treat as upper bounds; `ready` and `kernel-ready` coincide):

| Fixture | First frame = `ready` | First output | Last execution completed | Run span |
| --- | --- | --- | --- | --- |
| smoke-100 | 1,995 | 2,117 | 2,414 | 420 |
| smoke-500 | 3,310 | 3,624 | 4,553 | 1,215 |
| smoke-2000 | 14,092 | 14,168 | 20,083 | 5,590 |
| outputs-500 | 3,957 | 4,125 | 5,688 | 1,435 |

The whole snapshot (all `cell` frames, `document`, `runtime` …) arrives in one
burst within ~4 ms of `ready`; the socket is silent before that.

### M3. Compression

`permessage-deflate; server_max_window_bits=12; client_max_window_bits=12` **is
negotiated** when the client offers it (browsers always do). It comes from
uvicorn's default `ws_per_message_deflate=True`
(`uvicorn/protocols/websockets/websockets_sansio_impl.py:96-104`,
`memLevel=5`); marimo does not configure it (`marimo/_server/start.py:421-441`).

Offline recompression of the recorded frames (`compress_offline.py`, CPU):

| Scheme | smoke-500 bytes | % of raw | CPU | outputs-500 % |
| --- | --- | --- | --- | --- |
| raw JSON | 1,567,720 | 100% | | 100% |
| deflate, shared context, wbits 12 / mem 5 (**current**) | 238,050 | 15.2% | 25 ms (9.1 µs/frame) | 17.0% |
| deflate, shared context, wbits 15 / mem 8 | 222,443 | 14.2% | 31 ms | 13.5% |
| deflate per message (no context takeover) | 828,446 | 52.8% | 45 ms | 51.7% |
| zstd-3 per message | 876,507 | 55.9% | 15 ms | 54.9% |
| zstd-3 per message + 16 KB trained dictionary | 376,168 | 24.0% | 5 ms | 25.1% |
| zstd-3 streaming | 181,824 | 11.6% | 5 ms | 11.2% |
| brotli-4 streaming | 183,953 | 11.7% | 33 ms | 11.4% |
| whole trace as one gzip-6 blob (batching bound) | 172,235 | 11.0% | 14 ms | 10.5% |

In-server, `PerMessageDeflate.encode` costs 46 ms CPU for 2,788 frames at 500
cells (16.6 µs/frame), 5% of the event loop's CPU during run-all.

### M4. Server CPU per kernel message (run-all)

`probe_run.py` → `server_probe.py` (monkeypatched thread-CPU timers; no source
edits). smoke-500, first run-all, 3,012 kernel messages → 2,781 frames:

| Where (event-loop thread) | Calls | CPU ms | µs/call | Share |
| --- | --- | --- | --- | --- |
| whole event-loop thread, first → last kernel message | | **951** | 316 / kernel msg | 100% |
| `_on_kernel_message` (decode, view, translate, publish) | 3,012 | 696 | 231 | 73% |
| `deserialize_kernel_message` ×3 (view + backend + stream) | 9,040 | 312 | 34.6 | 33% |
| `copy.deepcopy` in `marimo/_core/stream.py` | 11,112 | 234 | 21.1 | 25% |
| `PerMessageDeflate.encode` | 2,788 | 46 | 16.6 | 5% |
| `serialize_event` | 2,781 | 11.5 | 4.1 | 1% |

That is 1.9 ms of event-loop CPU per cell executed. The same breakdown at
2000 cells (second run-all, 16,015 kernel messages): `_on_kernel_message`
4,220 ms, decodes 1,699 ms, deep copies 1,292 ms.

A/B with the two fixes monkeypatched in (`ab_run.py`, interleaved rounds,
frames and bytes byte-identical in every arm):

| Arm (smoke-500, 3 rounds) | Event-loop CPU ms, median (min) | Kernel-message span ms, wall median |
| --- | --- | --- |
| baseline | 930 (859) | 1,731 |
| cached `msgspec.json.Decoder` | 670 (653) | 1,850 |
| no deep copy in `Stream` | 729 (701) | 1,785 |
| **both** | **430 (419)** | **1,028** |

| Arm (smoke-2000, 2 rounds) | Event-loop CPU ms, median (min) | Kernel-message span ms, wall median |
| --- | --- | --- |
| baseline | 3,974 (3,859) | 5,667 |
| cached `msgspec.json.Decoder` | 2,762 (2,618) | 4,239 |
| no deep copy in `Stream` | 3,106 (3,047) | 4,529 |
| **both** | **1,972 (1,853)** | **3,987** |

The span shrinking 41% (500 cells) and 30% (2000 cells) shows the server relay
throttles the kernel: the kernel blocks on its pipe while the event loop is
busy.

Microbenchmarks, CPU, on recorded messages:

| What (`script`) | Result |
| --- | --- |
| `msgspec.json.decode(msg, type=NotificationMessage)` per call (`bench_decoder.py`) | 27.0 µs/msg |
| cached `msgspec.json.Decoder(NotificationMessage).decode` | 0.55 µs/msg (**49×**) |
| `copy.deepcopy(RoutedEvent)` (`bench_stream.py`) | 19.4 µs/event |
| `msgspec.json.encode(event)` | 0.84 µs/event |
| `Stream` publish + fan-out, 1 / 2 / 3 / 5 listeners | 57 / 78 / 104 / 127 µs/event |
| same, deep copies removed, 2 listeners | 1.6 µs/event |
| `send_text` per frame, real uvicorn stack (`bench_ws_send.py`), 2,781 frames | 94 ms (34 µs/event) |
| same events coalesced 16 per frame (174 frames) | 24 ms (8.7 µs/event) |
| `await asyncio.wait_for(q.get(), 20)` vs `await q.get()` (`bench_loop_overheads.py`) | +1.8 µs ready, +8.5 µs when it suspends |
| `pickle.loads` of a kernel message | 0.25 µs |
| `loop.call_soon_threadsafe` vs `call_soon` | 1.47 vs 0.64 µs |

### M5. Client → server requests

`scenarios.py PORT FIXTURE`: one editor tab stays connected; each action is an
HTTP request built from the frontend source, then the WebSocket frames it
triggers are counted. HTTP ms are client wall (min / median); "server CPU" is
the probe's thread CPU inside the handler.

| Action (endpoint) | | 100 cells | 500 cells | 2000 cells |
| --- | --- | --- | --- | --- |
| **Type in a cell** (`edits`, `replace_cell`) | request / response bytes | 1,667 / 1,097 | 1,264 / 3,897 | 1,939 / 14,397 |
| | WS frames / bytes pushed back | 5 / 12,533 | 5 / 44,329 | 5 / 167,933 |
| | HTTP ms min / median | 29 / 41 | 131 / 166 | 411 / 476 |
| | `SessionBridge.edit` CPU ms (event loop) | 23.8 | 115.8 | 409.6 |
| | — of which `code_fingerprint` calls / ms | 102 / 21.0 | 502 / 103.9 | 2,002 / 339.9 |
| | `CellAnalyzer` CPU ms (worker thread) | 3.9 | 24.1 | 240.4 |
| **Save** (`save`, body `{}`), after one edit | HTTP ms min / median | 206 / 393 | 916 / 1,500 | 3,320 / 3,702 |
| | `_write` worker-thread CPU ms | 192 | 788 | 2,869 |
| | `code_fingerprint` calls in edit + save | 304 | 1,504 | 6,004 |
| **Run one cell** (`runtime/runs`) | request / response bytes | 25 / 217 | 25 / 217 | 25 / 217 |
| | WS frames / bytes | 14 / 5,091 | 14 / 7,901 | 14 / 18,411 |
| | — of which `variables` bytes | 977 | 3,777 | 14,277 |
| | HTTP ms min / median | 4.0 / 4.1 | 4.2 / 19 | 8.7 / 12.7 |
| | `Notebook.run` CPU ms | 1.25 | 4.5 | 5.7 |
| **Create cell** (`create_cell` + `set_order`) | request / response bytes | 871 / 1,122 | 3,671 / 3,922 | 14,171 / 14,422 |
| | WS bytes | 10,630 | 46,033 | 178,787 |
| | HTTP ms min | 33 | 128 | 439 |
| **Delete cell** | request bytes / WS bytes | 862 / 11,110 | 3,662 / 49,313 | 14,162 / 192,567 |
| **Toggle hide_code** (`replace_cell`) | WS bytes / HTTP ms min | 11,227 / 23 | 43,427 / 144 | 166,356 / 470 |
| **Run all again** | WS frames / bytes | 732 / 285,845 | 3,530 / 1,264,717 | 14,032 / 5,074,758 |
| **Format one cell** (`/api/kernel/format`) | HTTP ms min | 150 | 297 | 165 |
| **Format all cells** | request / response bytes | 68,625 / 66,069 | 369,438 / 355,922 | not run |
| | HTTP ms (wall, one run) | 12,019 | 72,599 (outputs-500: 52,173) | (extrapolated: 4–5 min) |
| **Completion** (`code_autocomplete`, `json.du`) | request bytes / WS result bytes | 78 / 12,759 | 78 / 12,759 | 78 / — |

CPU scaling of the edit and save paths in isolation (`bench_edit_path.py`,
`process_time`, medians):

| Cells | `documents.sources()` = n × `code_fingerprint` | `save_from_cells` (codegen + write) | `CellAnalyzer` cold / per edit | `analysis` record |
| --- | --- | --- | --- | --- |
| 101 | 23.8 ms | 78 ms | 66 / 2.6 ms | 7.6 KB |
| 501 | 116.2 ms | 422 ms | 420 / 21.2 ms | 37.4 KB |
| 2,001 | 461.4 ms | 2,313 ms | 2,440 / 318.6 ms | 149.2 KB |

`sources()` and codegen are linear (exponent 0.99 and 1.13); the per-edit
analysis is super-linear (exponent 1.95 from 500 to 2000).

Format, 101 cells (`bench_ruff.py`, wall, min of 2–3):

| Strategy | Wall | Per cell |
| --- | --- | --- |
| one `python -P -m ruff format -` per cell, sequential (**current**) | 6,825 ms | 67.6 ms |
| one `ruff` binary per cell | 2,431 ms | 24.1 ms |
| one `ruff format` process over temp files | 167 ms | 1.7 ms (**41×**) |

### M6. Reconnect, resume, second tab

Same `scenarios.py` run, after the edits and a second run-all.

| Scenario | | 100 cells | 500 cells | 2000 cells |
| --- | --- | --- | --- | --- |
| Same `session_id`, **with cursor** | frames / bytes | 9 / 3,089 | 9 / 7,289 | 9 / 23,042 |
| Same `session_id`, no cursor (page reload) | frames / bytes | 320 / 206,793 | 1,520 / 1,040,439 | 6,020 / 4,234,830 |
| | ms to `ready`, wall | 69 | 279 | 593 |
| | `Host.events` CPU ms | | 34 | 121 |
| Second tab while the first is connected | frames / bytes | 321 / 207,301 | 1,521 / 1,040,947 | 6,021 / 4,235,338 |
| New `session_id` (resume) | frames / bytes | 321 / 207,268 | 1,521 / 1,040,914 | 6,021 / 4,235,305 |

The replay is proportional to **current state**, not history: per cell one
`cell`, one completed `execution`, one `output` (3.0 frames, ~2.1 KB per cell).
With a cursor only the missed events are sent, but the log holds 1,000 events
(`marimo/_core/stream.py:221`), fewer than one run-all of 500 cells (2,274
live events), so a client that disconnects during run-all gets `reset` + full
snapshot.

## Findings (highest impact first)

### F1. Every edit re-fingerprints (AST-parses) every cell on the event loop

- **Category:** algorithms, caching
- **Where:** `marimo/_server/host/bridge.py:606` (`SessionBridge._mirror`) →
  `marimo/_server/host/document.py:53` (`from_session`) → `:62` (`sources`) →
  `marimo/_core/document.py:97` (`DocumentCell.__post_init__`) →
  `marimo/_core/code.py:18` (`code_fingerprint`: `ast.parse` + `ast.dump` +
  SHA-256). Reached on every `notebook.edit` via
  `marimo/_server/host/bridge.py:443` (`apply_to_session`) →
  `marimo/_server/host/backend.py:532-535` (`_document_changed`).
- **Evidence:** MEASURED. Per edit: 102 / 502 / 2,002 `code_fingerprint` calls
  and 23.8 / 115.8 / 409.6 ms of event-loop CPU at 100 / 500 / 2000 cells
  (M5); 90% of `SessionBridge.edit` is `code_fingerprint`. HTTP latency of a
  one-line edit: 131 ms min at 500 cells, 411 ms at 2000.
- **Why it is slow:** the bridge rebuilds the whole host document from the
  session's cells after each transaction, and each `DocumentCell` recomputes
  its fingerprint from source. The frontend sends edits back-to-back while the
  user types (`frontend/src/core/notebook/document/sync.ts:45`, 100 ms first
  batch, then one request per confirmation), so the event loop is busy almost
  continuously while typing. Outputs, completions and every other request
  queue behind it.
- **Proposed fix:** (a) smallest: memoize `code_fingerprint` by source
  (`../patches/wire-code-fingerprint-cache.patch`,
  `functools.lru_cache`). (b) better: make `_mirror` incremental — reuse the
  previous `DocumentCell` when `code`, `name`, `config` are unchanged (identity
  check on the session cell), or apply the session transaction's changes to
  the host document instead of rebuilding it. (c) best: remove the second
  document (the TODO at `marimo/_server/host/bridge.py:91-93`).
- **Expected impact:** MEASURED with (a) monkeypatched
  (`bench_fingerprint_cache.py`): `sources()` per edit 21.1 → 0.8 ms (100),
  116.7 → 4.6 ms (500), 447 → 16.4 ms (2000), 25–27×. (b) removes the
  remaining O(n) hashing. Also removes 2 of the 3 passes at session start (F9)
  and both passes per save (F4).
- **Effort / risk:** S for (a); the cache holds source strings (bound it; 8,192
  entries ≈ a few MB). M for (b).

### F2. The server decodes each kernel message three times with an uncached union decoder

- **Category:** caching
- **Where:** `marimo/_messaging/serde.py:24-31`
  (`deserialize_kernel_message`: `msgspec.json.decode(..., type=NotificationMessage)`),
  called per message from `marimo/_session/state/session_view.py:296`
  (`add_raw_notification`), `marimo/_server/host/backend.py:519`
  (`SessionBackend.notify`) and `marimo/_server/host/session.py:98`
  (`SessionEventStream.notify`); plus a fourth partial decode at
  `marimo/_session/extensions/extensions.py:303`.
- **Evidence:** MEASURED. 27.0 µs per call vs 0.55 µs with a prebuilt
  `msgspec.json.Decoder` (49×, `bench_decoder.py`). In-server: 312 ms of 951 ms
  event-loop CPU during run-all at 500 cells; 1,699 ms at 2000 (M4). A/B:
  930 → 670 ms (−28%).
- **Why it is slow:** `msgspec.json.decode(type=<Union>)` rebuilds the lookup
  for the 48-member tagged union on every call. Each kernel message is then
  decoded independently by three consumers.
- **Proposed fix:** build the decoder once
  (`../patches/wire-cached-notification-decoder.patch`). Then decode
  once in `SessionImpl.notify` (`marimo/_session/session.py:485`) and pass the
  decoded notification to the view and consumers instead of bytes. Audit the
  other per-call union decodes: `marimo/_utils/parse_dataclass.py:207`,
  `marimo/_ipc/types.py:54`.
- **Expected impact:** −28% event-loop CPU for run-all at 500 cells and −30% at
  2000 from the patch alone. Combined with F3: 930 → 430 ms (−54%) at 500
  cells and 3,974 → 1,972 ms (−50%) at 2000; the run's wall span drops
  1,731 → 1,028 ms and 5,667 → 3,987 ms.
- **Effort / risk:** S. Behaviour-preserving (frames byte-identical in A/B).

### F3. The host stream deep-copies every event four times

- **Category:** datastructures, streaming
- **Where:** `marimo/_core/stream.py:172` (`Sink.publish`: `deepcopy(body)`),
  `:320` (`Stream._append`: `return deepcopy(stamped)`), `:329`
  (`Stream._drain`: `listener(deepcopy(pending))`, once per listener, before
  the listener's own filter runs), `:38` (`snapshot_event`), `:271`
  (`Stream.since`); also `marimo/_core/executions.py:283` (`_records`).
- **Evidence:** MEASURED. 11,112 deep copies for 2,779 events (4.0 per event)
  = 234 ms of 951 ms event-loop CPU at 500 cells; 1,292 ms at 2000. One
  `deepcopy` of an event is 19.4 µs; encoding it to JSON is 0.84 µs
  (`bench_stream.py`). Each extra subscriber (second tab, `marimo pair`,
  SSE client) adds one more copy per event: 57 / 78 / 104 / 127 µs per event
  at 1 / 2 / 3 / 5 listeners. A/B: 930 → 729 ms (−22%).
- **Why it is slow:** `copy.deepcopy` walks msgspec structs through the
  generic `__reduce__` path. Two listeners exist with one tab (the bridge and
  the connection), and the bridge's listener only wants `notebook` events but
  still receives a copy of every event.
- **Proposed fix:** every protocol struct is `frozen=True`; the only mutable
  payloads are a few dicts (`app_config`, `depends_on`, `Analysis.cells`).
  Options: (a) stop copying frozen structs, and freeze/copy only those dict
  fields at publish; (b) serialize once at `_append` and fan out bytes — the
  WebSocket listeners only need text, and only `cell` events vary per
  connection (`include_code`, `marimo/_server/host/events.py:152`); (c) at
  least filter before copying in `_drain` and drop the unused return copy.
- **Expected impact:** MEASURED with copies disabled: −22% event-loop CPU alone
  at both 500 and 2000 cells, −54% / −50% with F2. Per event 78 → 1.6 µs in isolation. Snapshot/replay (F10)
  drops two full copies of the notebook state.
- **Effort / risk:** M. The copies are the stream's isolation guarantee;
  (b) keeps it by construction. Needs a test that listeners cannot mutate the
  log.

### F4. Save recompiles every cell and fingerprints the notebook twice

- **Category:** caching, algorithms
- **Where:** `marimo/_server/host/bridge.py:275` (`save`) → `:360` (`_write`)
  → `marimo/_session/notebook/file_manager.py:456` (`save_from_cells`) →
  `marimo/_ast/codegen.py:642` (`TopLevelExtraction.from_codes`) →
  `marimo/_ast/toplevel.py:125` (`compile_cell` for every cell). Then
  `marimo/_server/host/bridge.py:375-377` (`Document(documents.sources(cells))`)
  and again in the `on_persisted` callback at `:541-548`.
- **Evidence:** MEASURED. Save after one edit: 0.9–1.5 s wall at 500 cells,
  3.3–3.7 s at 2000; worker-thread CPU 788 / 2,869 ms (M5). Profile at 500
  cells (`prof-save_from_cells-smoke-500.txt`): 86% of `save_from_cells` is
  `compile_cell` inside `TopLevelStatus.update`; file write is negligible. One
  edit + save runs `code_fingerprint` 3n times (1,504 calls at 500).
- **Why it is slow:** codegen needs each cell's defs/refs to decide the
  function signature, and compiles every cell from scratch on every save; the
  host then builds two throwaway `Document`s just to compute an etag.
  Autosave fires 1 s after every confirmed change
  (`frontend/src/core/saving/useAutoSave.ts:28`, `autosave_delay` 1000), so a
  typing session triggers this continuously. It runs in a thread but holds the
  GIL, so it competes with the event loop.
- **Proposed fix:** cache the per-cell codegen input (compiled `CellImpl` or
  just `defs`/`refs`/top-level status) by source — the session's cell manager
  and the host `CellAnalyzer` (`marimo/_server/host/analysis.py:65`) already
  hold compiled cells for unchanged sources. Compute the saved etag once, from
  the `Document` the host already has when the session document equals it.
  F1's fingerprint cache removes the 2n fingerprints.
- **Expected impact:** codegen 422 → ~60 ms at 500 cells (the non-compile 14%
  plus one changed cell), 2,313 → ~330 ms at 2000; plus −230 / −920 ms of
  fingerprinting. Save drops from ~0.9 s to ~0.1 s at 500 cells.
- **Effort / risk:** M. Cache invalidation is by exact source, low risk. The
  `backend-load-save` investigator may cover codegen in more depth.

### F5. Every edit rebroadcasts the whole `analysis` and `document` records

- **Category:** streaming, algorithms, batching
- **Where:** `marimo/_core/notebook.py:310-311` (`_publish_changed` →
  `_request_analysis`), `:339-347` (`_analyze` publishes a new
  `protocol.Analysis` for all cells unconditionally), `:145-157`
  (`_document_record` carries the full `order`);
  `marimo/_server/host/analysis.py:71-90` (`CellAnalyzer.__call__` rebuilds a
  `DirectedGraph` for all cells).
- **Evidence:** MEASURED. One-line edit pushes 5 frames: 12.5 KB at 100 cells,
  44.3 KB at 500, 167.9 KB at 2000 (M5). `analysis` is 85–89% of that
  (37.6 KB / 149.3 KB), `document` 3.9 / 14.4 KB, and the HTTP response repeats
  the document (3.9 / 14.4 KB). The analysis content does not change when a
  comment is typed. The analyzer costs 24 ms per edit at 500 cells and 240 ms
  at 2000 (super-linear, exponent ~1.7–1.95; the profile is all
  `DirectedGraph.register_cell` → `compute_edges_for_cell`).
- **Why it is slow:** records are whole-object snapshots keyed by notebook, so
  any document revision republishes an O(n) record; the graph is rebuilt
  rather than updated. The client must `JSON.parse`, validate and reduce a
  150 KB record per keystroke batch at 2000 cells.
- **Proposed fix:** (a) do not publish `analysis` when the per-cell analyses
  are equal to the last published ones (compare `cells`, ignore
  `document_etag`), or publish per-cell analysis records so one changed cell
  is one small record. (b) Keep the `DirectedGraph` across revisions and
  re-register only cells whose source changed. (c) Send `order` only when
  `order_etag` changes (a `document` record without `order`, or a separate
  `order` record).
- **Expected impact:** typing edit 44.3 KB → ~3 KB at 500 cells, 167.9 KB →
  ~4 KB at 2000 (`cell` + transaction + a `document` without order). Analyzer
  24 → ~1 ms, 240 → ~1 ms per edit.
- **Effort / risk:** M (a, b); L for (c), a protocol change that clients must
  understand.

### F6. Format spawns one Python interpreter per cell, sequentially

- **Category:** batching
- **Where:** `marimo/_utils/formatter.py:64-106` (`ruff`): a
  `python -P -m ruff --help` probe at `:68-71`, then
  `python -P -m ruff format -` per cell in a `for` loop at `:85-94`.
- **Evidence:** MEASURED. Format-all over HTTP: 12.0 s at 100 cells, 72.6 s
  and 52.2 s at 500 cells (wall, loaded machine). In isolation, 101 cells:
  6.8 s current vs 0.17 s with one `ruff format` process (41×,
  `bench_ruff.py`). Even one cell costs 150–460 ms.
- **Why it is slow:** each cell pays interpreter startup plus `ruff` exec, and
  cells are awaited one at a time. "Format all" and `format_on_save`
  (`frontend/src/core/saving/save-component.tsx:126`) format every cell.
- **Proposed fix:** resolve the binary once (`ruff.__main__.find_ruff_bin()`,
  cached) and run **one** process for all cells: write the wrapped cells to a
  temp directory and run `ruff format <dir>`, or run the per-cell commands
  concurrently under a semaphore as a smaller step. Skip the `--help` probe
  after the first success.
- **Expected impact:** format-all at 500 cells ~50–70 s → ~1 s; single cell
  ~150 ms → ~25 ms (binary, no interpreter).
- **Effort / risk:** S–M. Temp-file route must keep `--stdin-filename`
  semantics (config discovery); pass `--config`/cwd explicitly.

### F7. One WebSocket frame per event, no coalescing

- **Category:** batching, streaming
- **Where:** `marimo/_server/host/session.py:196-218` (`stream`: one
  `asyncio.wait_for(self._events.get(), ...)` per event) and `:248`
  (`await websocket.send_text(...)` per event);
  `marimo/_core/stream.py:322-333` (`_drain` delivers event by event).
- **Evidence:** MEASURED. 2,781 frames at 500 cells, 11,031 at 2000; a second
  run-all is 3,530 / 14,032. 2,274 live frames at 500 cells arrive in 64
  distinct 16 ms windows (~36 per window) in the least-loaded run; 9,024 in
  250 windows at 2000 cells. Server send loop: 34 µs per frame
  one-by-one vs 8.7 µs per event when 16 are coalesced (`bench_ws_send.py`):
  94 → 24 ms at 500 cells. `wait_for` adds 1.8–8.5 µs per event. INFERRED for
  the client: each frame is parsed, zod-validated
  (`packages/client/src/transport/stream.ts:139-151`) and reduced into the
  store separately (`frontend/src/core/notebook/replica/replica.ts:442`), so
  frame count is the number of store transactions.
- **Why it is slow:** per-frame fixed costs (task wake-up, starlette → uvicorn
  → websockets framing, a `write` syscall, a browser `onmessage` task) are paid
  5.5 times per cell.
- **Proposed fix:** drain the queue with `get_nowait()` after each wake-up and
  send everything available as one frame (JSON array or newline-delimited
  events; the client loops). Optionally a ≤10 ms flush window. Replace the
  per-event `wait_for` with a heartbeat timer. The snapshot before `ready`
  (505 frames at 500 cells) is already available all at once and should be one
  frame.
- **Expected impact:** frames per run-all at 500 cells 2,781 → ~200–700;
  server send CPU −70 ms (of ~430 ms after F2/F3). The larger win is expected
  in the browser (fewer tasks and store commits) and needs a browser
  measurement.
- **Effort / risk:** M. Needs a client that accepts batched frames (protocol
  version or capability flag).

### F8. Execution lifecycle is three full records plus bookkeeping frames per cell

- **Category:** streaming, datastructures
- **Where:** `marimo/_core/executions.py:585-622` (`_observe_planned`),
  `:624-648` (`_observe_started`), `:410-430` (`Completed`) — each publishes
  the whole `protocol.Execution`; `marimo/_server/host/translate.py:152-158`
  (`Displayed(execution.id, None)` for an empty output);
  `marimo/_runtime/runtime.py:1290` (`RemoveUIElementsNotification` per cell
  run); `marimo/_core/executions.py:689-726` (re-run publishes
  `output.removed` + `execution.removed`).
- **Evidence:** MEASURED at 500 cells. `execution` events are 785,882 bytes
  (50% of all traffic, 1,569 B per cell). `code_fingerprint` (79 chars) is
  repeated in all three: 151,803 bytes; three UUIDs per event: 145,791 bytes.
  Encoding `running`/`completed` as `{id, state}` patches would save 343,945
  bytes (44% of execution bytes). 251 `output` frames carry `media: null`
  (code cells with no output); 251 `remove-ui-elements` frames for cells that
  never had UI elements. A second run-all adds 2 removal frames per cell
  (7.0 frames per cell instead of 5.5).
- **Why it is slow:** the protocol publishes whole records on every state
  transition. After deflate the byte cost is small (shared context), but the
  frame count and client-side parse/reduce work is not.
- **Proposed fix:** (a) skip the `output: null` event when the execution never
  displayed anything; (b) emit `remove-ui-elements` only when the cell
  registered UI elements; (c) fold `queued` into `running` when both happen in
  the same tick, or publish state patches; (d) let a new execution for a cell
  implicitly replace the old one instead of two explicit removals.
- **Expected impact:** frames per cell 5.5 → 3–3.5 on first run and 7.0 → 4 on
  re-run (−40%); JSON bytes −25–30%. With F7 the remaining frames coalesce.
- **Effort / risk:** S for (a), (b); M–L for (c), (d) (protocol semantics).

### F9. Session start does O(notebook) work several times before the first frame

- **Category:** caching, lazy-init, streaming
- **Where:** `marimo/_server/session_manager.py:354` (`_create_session`) →
  `marimo/_session/notebook/file_manager.py:258` (`_load_app`: parse + compile
  every cell, on the event loop); `marimo/_server/host/bridge.py:216`
  (`_initialize_notebook` → `from_session`), `:502` (`_attach_document` →
  `from_session`), `marimo/_session/session.py:534-538` (`instantiate` →
  `ExecuteCellCommand.__post_init__`, `marimo/_runtime/commands.py:270`) —
  three `code_fingerprint` passes; `marimo/_cli/utils.py:128`
  (`check_app_correctness`) parses the notebook a second time at CLI start;
  `marimo/_server/host/analysis.py:79` compiles every cell again in a thread.
- **Evidence:** MEASURED. First frame (`ready`) arrives 2.0 / 3.3 / 14.1 s
  after connect at 100 / 500 / 2000 cells (wall, loaded). pyinstrument of the
  event loop at 2000 cells (`profbase-smoke-2000.profile.txt`, inflated by the
  profiler): `load_app` 6.5 s (compile 3.2 s, parse 2.9 s), three fingerprint
  passes 3.3 s, kernel start 2.3 s, initial publish deep copies 0.6 s. In CPU
  terms one fingerprint pass is 116 ms at 500 cells and 449 ms at 2000, so the
  three passes are 0.35 s / 1.35 s. Nothing is sent before all of it finishes.
- **Why it is slow:** each layer (CLI check, file manager, host document,
  session instantiate, analyzer) derives the same per-cell facts from source
  independently, synchronously on the event loop.
- **Proposed fix:** F1's fingerprint cache (3 passes → 1). Pass the computed
  fingerprints into `ExecuteCellCommand`. Send the document snapshot (`cell`,
  `document`) as soon as the file is parsed, before the kernel starts and
  before analysis, so the editor can paint while the runtime boots. Reuse the
  compile done by `load_app` in the analyzer.
- **Expected impact:** −0.23 s / −0.9 s CPU before first frame at 500 / 2000
  cells from the cache alone; sending the snapshot before kernel start removes
  the kernel-start wait (~1–2 s) from time-to-first-paint.
- **Effort / risk:** S (cache), M (early snapshot). Parse/compile cost itself
  belongs to the load investigation.

### F10. Reconnect, second tab and resume replay the whole state as ~3n frames

- **Category:** streaming, batching
- **Where:** `marimo/_core/host.py:276-301` (`_snapshot`),
  `marimo/_core/notebook.py:772-782` (`_snapshot`),
  `marimo/_core/executions.py:281-297` (`_records` deep copy) and
  `marimo/_core/stream.py:38` (`snapshot_event` deep copy again);
  `marimo/_server/host/session.py:156-163` (one queue item, then one frame,
  per record).
- **Evidence:** MEASURED. Page reload at 500 cells: 1,520 frames, 1,040,439
  bytes, `ready` after 279 ms; at 2000 cells: 6,020 frames, 4.23 MB, 593 ms.
  Server CPU at 2000: `Host.events` 121 ms + deflate 107 ms + snapshot deep
  copies 64 ms. A second tab costs the same.
- **Why it is slow:** each record is copied twice and sent as its own frame;
  `cell` records carry source the client may already hold.
- **Proposed fix:** send the snapshot as one frame (F7) built with one encode
  and no deep copies (F3). Raise the replay log above one run-all, or size it
  by notebook (history 1,000 < 2,274 events for a 500-cell run), so a
  reconnect during a run resumes instead of resetting. Optionally let the
  client send the etags it holds so unchanged `cell` records are skipped.
- **Expected impact:** frames 1,520 → 1; server CPU for the snapshot roughly
  halved; no reset on mid-run reconnects.
- **Effort / risk:** M.

### F11. Static assets: no `Cache-Control`, no compression

- **Category:** caching, compression
- **Where:** `marimo/_server/api/endpoints/assets.py:113-120` (bare
  `StaticFiles` mount); `marimo/_server/main.py:70-131` (no compression
  middleware).
- **Evidence:** MEASURED. Hashed assets are served with `etag` +
  `last-modified` only. First render needs 136 JS/CSS files, 4.81 MB raw
  (1.49 MB gzip, 1.39 MB brotli). Without `Cache-Control`, browsers use
  heuristic freshness (10% of the time since `last-modified`), so a recently
  installed or rebuilt marimo revalidates every file on each load: 136
  conditional requests, 399 ms wall here.
- **Why it is slow:** on localhost the bytes are cheap, but the request count
  is not, and over a remote/proxied deployment (SSH tunnel, hub, molab) 4.8 MB
  uncompressed dominates load time.
- **Proposed fix:** wrap the `/assets` mount to add
  `Cache-Control: public, max-age=31536000, immutable` (file names are content
  hashed). Serve precompressed `.br`/`.gz` siblings built by Vite, or add
  `GZipMiddleware(minimum_size=1024)` limited to HTTP (it must skip
  `text/event-stream`; WebSockets are unaffected).
- **Expected impact:** reload: 136 requests → 0 for cached assets. Remote
  first load: 4.81 MB → 1.4–1.5 MB.
- **Effort / risk:** S. `immutable` is safe only for hashed names; keep
  `index.html` on `no-cache`.

### F12. Source is shipped kernel → server on every run, and server → kernel on every run request

- **Category:** streaming
- **Where:** `marimo/_runtime/execution.py:47-70` (`ExecutionAttempt.plan`
  puts `code` in the `planned` notification);
  `marimo/_server/host/backend.py:223-231` and `:261-276` (`run_cells` builds
  an `ExecuteCellCommand` for every cell and `_submit_cells` sends them all in
  a `CreateNotebookCommand` on each run).
- **Evidence:** MEASURED. 365,242 of 1,206,201 kernel → server bytes at 500
  cells (30%) are source echoed in `planned`, decoded three times (F2). Each
  run request pickles 361,992 bytes (500 cells) / 1,526,619 bytes (2000) to
  the kernel, which returns early (`marimo/_runtime/runtime.py:2803`).
  `Notebook.run` costs 4.5 / 5.7 ms CPU at 500 / 2000 cells for a one-cell run.
- **Why it is slow:** the translator keeps `code` only to map error columns
  (`marimo/_server/host/translate.py:68`), and the server already has it.
- **Proposed fix:** send `code` in `planned` only for scratch executions; look
  it up from the document otherwise. Send `CreateNotebookCommand` once per
  kernel, not per run.
- **Expected impact:** kernel → server bytes −30%; run request 362 KB → ~1 KB.
  A few ms per run; small next to F1–F3.
- **Effort / risk:** S–M.

### F13. `variables` is rebroadcast in full on every run

- **Category:** streaming
- **Where:** `marimo/_runtime/runtime.py:1537` (`VariablesNotification`).
- **Evidence:** MEASURED. Running one cell pushes 14 frames; `variables` is
  977 / 3,777 / 14,277 bytes of the 5.1 / 7.9 / 18.4 KB total (19% / 48% /
  78%). In a star graph each imported name lists every cell that uses it.
- **Why it is slow:** the full variable → cells map is sent whenever the graph
  is touched, even when unchanged.
- **Proposed fix:** skip the broadcast when the map equals the last one sent;
  or send per-variable deltas.
- **Expected impact:** single-cell run 7.9 → 4.1 KB at 500 cells, 18.4 → 4.1 KB
  at 2000.
- **Effort / risk:** S.

### F14. Retained state that only grows

- **Category:** datastructures
- **Where:** `marimo/_session/state/session_view.py:405`
  (`cell_notifications`, never removed when a cell is deleted — no `pop`/`del`
  anywhere in `marimo/`), `:248` (`last_executed_code`), `:597-606`
  (`ui_element_messages`, an append-only list per element, replayed on every
  connect; the code carries a TODO); `marimo/_core/stream.py:221-226` (history
  bounded by count, 1,000 events, not bytes).
- **Evidence:** INFERRED from code. Not observed as a problem in these
  fixtures (reconnect bytes matched current state).
- **Why it is slow:** deleted cells keep their last output (up to
  `output_max_bytes`, 8 MB) for the session's lifetime; the history can pin
  1,000 large outputs (a slider re-rendering a plot).
- **Proposed fix:** drop view entries on `DeleteCell`; cap
  `ui_element_messages` per element; bound the history by bytes as well.
- **Expected impact:** memory only; prevents slow growth in long sessions.
- **Effort / risk:** S.

### F15. Paper cuts

- **Category:** batching, caching
- `marimo/_server/host/session.py:198-200`: `asyncio.wait_for` per event
  (MEASURED +1.8–8.5 µs each; 5–24 ms per 500-cell run). Use one heartbeat
  timer.
- `marimo/_core/stream.py:329`: the bridge's listener receives a deep copy of
  every event and then discards all but `notebook` events
  (`marimo/_server/host/bridge.py:134-136`). Filter first.
- Completion results: one request returns a 12,759-byte `completion-result`
  frame (MEASURED, `json.du`); docs for every option are sent eagerly.
- `set_order` sends every cell id for one insert/delete (MEASURED 3.7 KB
  request at 500 cells, 14.2 KB at 2000) and the response repeats the order.
  An `insert after`/`move` change would be O(1).
- `index.html` embeds the user config twice (`<marimo-user-config>` 3.9 KB and
  the mount config), ~15% of the 25 KB page (MEASURED).
- `marimo/_server/host/notebook_api.py:138`: each notebook operation is
  encoded to JSON and decoded again to build the typed call (INFERRED, small).

## Ruled out

- **WebSocket compression is already on.** `permessage-deflate` is negotiated
  with context takeover; wire bytes are 15–18% of JSON. A larger window
  (wbits 15) gains 1–3.5 points; zstd/brotli streaming gain ~4–6 points. The
  encoder costs 16.6 µs/frame (5% of event-loop CPU). Not worth changing.
- **`kernel-ready` payload:** 455 bytes at every size.
- **`index.html`:** 25 KB, constant; the notebook is not inlined.
- **Full-notebook save/run/instantiate payloads:** gone. Save body is `{}`,
  run body is 25 bytes, edits carry one cell.
- **O(n²) traffic:** none. Bytes and frames scale with exponent 1.00 / 0.99
  from 100 to 2000 cells; no per-cell rebroadcast during a run.
- **Lazy-loading source for hidden-code markdown cells:** their source is
  35,972 of 526,959 `cell` bytes at 500 cells (6.8%). Not worth a protocol
  change.
- **Pickle on the kernel pipe** (`marimo/_utils/distributor.py:77-79` TODO):
  0.25 µs per message.
- **`loop.call_soon_threadsafe` per kernel message**
  (`marimo/_session/extensions/extensions.py:411`): 1.5 µs.
- **`serialize_event`:** 4.1 µs/event (11.5 ms per 500-cell run).
- **Reconnect with a cursor:** 9 frames, 3–23 KB.
- **Run-one-cell request latency:** 4–19 ms wall at every size.
- **`SessionView.snapshot_notifications`:** 0.2–0.6 ms; the editor scope no
  longer replays per-cell notifications.

## Could not measure

- Browser-side cost per frame (parse, zod validation, store commit). F7/F8
  quantify frames and server CPU only.
- Clean wall-clock timelines: the machine never dropped below load ~27. The
  timeline in M2 and all HTTP ms are upper bounds; CPU numbers and ratios are
  the reliable part.
- `py-spy` (needs root on macOS); pyinstrument and in-process thread-CPU
  timers were used instead.
- Format-all at 2000 cells (extrapolated from the per-cell cost).
- Remote/proxied latency effects of F11.

## Benchmarks added

Reusable, in the repo:

- `scripts/benchmarks/ws_traffic.py` — connects to a running `marimo edit`
  server as the frontend does and prints frames/bytes per event kind, bytes on
  the wire, and milestones.
  `python scripts/benchmarks/ws_traffic.py http://127.0.0.1:2718 --expect-run --out trace.jsonl`
  (`--session-id`, `--cursor`, `--kiosk`, `--no-deflate` for reconnect and
  compression experiments).

Proposed patches (not applied; both pass `git apply --check`):

- `../patches/wire-cached-notification-decoder.patch` (F2)
- `../patches/wire-code-fingerprint-cache.patch` (F1, F4, F9)

Scratch, in `.context/perf/wire-protocol/` (run with `.venv/bin/python` from
that directory; servers use ports 29821–29824 and are killed on exit):

| Script | What it does |
| --- | --- |
| `harness.py` | start/stop a server for a fixture copy in `nb/` |
| `matrix.py PORT RUNS FIXTURE…` | first-connect traffic and timeline (M2) |
| `analyze_trace.py trace-X.jsonl` | per-kind and redundancy breakdown |
| `compress_offline.py trace-X.jsonl` | M3; `uv run --no-project --with zstandard --with brotli python …` |
| `server_probe.py` | wraps the `marimo` CLI with thread-CPU timers, optional pyinstrument profile, raw kernel-message capture, and `PROBE_FIX=decoder,nodeepcopy` |
| `probe_run.py PORT FIXTURE` | M4 table |
| `ab_run.py PORT FIXTURE ROUNDS` | M4 A/B |
| `scenarios.py PORT FIXTURE` | M5 and M6 |
| `bench_decoder.py`, `bench_kernel_msgs.py`, `bench_stream.py`, `bench_ws_send.py`, `bench_loop_overheads.py` | M4 microbenchmarks (inputs: `probe-smoke-100.kernel.jsonl`, `trace-smoke-*.jsonl`) |
| `bench_edit_path.py`, `bench_fingerprint_cache.py`, `prof_save.py`, `bench_ruff.py` | M5 microbenchmarks and profiles |
| `assets.py` | M1 asset table |

Raw results: `matrix-loaded-run1.json` (M2 traffic table, all six fixtures),
`matrix-29821.json` (M2 timeline), `scenarios-*.json`, `ab-smoke-*.json`,
`trace-*.jsonl`, `prof*-*.profile.txt`, `prof-*.txt`, `post-runs.log`.
