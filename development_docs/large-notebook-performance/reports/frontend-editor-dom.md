# Per-cell editor cost and the DOM — large-notebook performance

Scope: CodeMirror setup, lazy initialization, DOM size, listeners/observers, CSS
selectors, output rendering. Target shape: 500 cells, half `hide_code` markdown
(`smoke-500`).

**How everything here was measured.** No browser was used (another investigator
owns that). Numbers come from (a) vitest + jsdom running the *real* production
modules and the *real* `<Cell>` component, (b) static analysis of source, and
(c) static analysis of the built CSS in `marimo/_static/assets`. jsdom caveats,
which apply to every timing below:

- jsdom has no style engine and no layout. Style recalculation, layout, paint
  and compositing cost are **not** measured anywhere in this report. Where a
  finding's cost is in the style/layout engine it is marked INFERRED and the
  mechanism is given so the browser investigator can confirm it.
- jsdom DOM operations are roughly an order of magnitude slower than Blink's,
  and jsdom parses CSS with a slow JS parser. Absolute milliseconds are
  therefore upper bounds; **counts, ratios and scaling exponents** are the
  results to rely on.
- Other investigators were benchmarking concurrently. Timings are medians of
  3–6 runs and still vary by ±30%.

## Measurements

### M1. Editor micro-benchmark (`frontend/benchmarks/large-notebook-editor.bench.ts`)

`cd frontend && pnpm exec vitest bench benchmarks/large-notebook-editor.bench.ts --mode test --run --no-file-parallelism`
Median of the per-run means over 6 runs, ms. Logs: `.context/perf/frontend-editor-dom/bench-run{1..6}.log`.

| Operation | 1 cell | 50 cells | 500 cells | Exponent 50→500 |
| --- | --- | --- | --- | --- |
| `setupCodeMirror()` (build extension array) | 0.13 | | | |
| `EditorState.create`, full bundle, 1 KB Python | 0.42 | | | |
| `EditorState.create`, full bundle, `mo.md(...)` source | 0.05 | | | |
| extensions + state + `EditorView` + `switchLanguage`, Python | 5.6 | | | |
| same, markdown | 3.7 | | | |
| Create every editor (half markdown) | | 229 | **5,212** | **1.36** |
| Create only the code editors (hidden markdown skipped) | | 147 | 2,207 | 1.18 |
| Reconfigure every editor (`handleReconfigureEditor`) | | 168 | **5,595** | **1.52** |
| One `selectionchange` event | | 0.43 | 5.9 | 1.14 |
| Language detection (`languageAdapterFromCode`) for every cell | | 0.31 | 3.4 | 1.03 |
| Static highlighted `<pre>` (lezer + `highlightTree`), per code cell | 1.8 | 41 | 528 | 1.10 |
| Plain `<pre>` | 0.005 | | | |

The benchmark resets CodeMirror's style set between samples; without that every
sample is slower than the last (see M2), which is itself finding F1.

### M2. CodeMirror stylesheet growth (`style-growth.test.ts`)

`cd frontend && [REAL_STYLE=1] [SHARE_THEMES=1] pnpm exec vitest run --config ../.context/perf/frontend-editor-dom/vitest.config.mts style-growth`
Creates 500 editors with the production bundle, then reconfigures all of them
twice. `SHARE_THEMES=1` is a prototype of the fix (memoizes `EditorView.theme` /
`baseTheme` by spec, i.e. what hoisting them to module constants does).
`REAL_STYLE=1` lets jsdom parse the `<style>` text on each write.

| | Today | Prototype fix |
| --- | --- | --- |
| Style modules mounted after 500 editors | 1,013 (13 shared + 2 per editor) | 15 |
| Rules / bytes in CodeMirror's `<style>` after 500 editors | 1,678 / 157 KB | 181 / 12.9 KB |
| `<style>.textContent` rewrites while creating 500 editors | 499 (each with the whole sheet) | 499 (identical text every time) |
| Cumulative CSS text assigned while creating 500 editors | 42.5 MB | 6.4 MB |
| After one notebook-wide reconfigure | 2,013 modules / 3,178 rules / 302 KB, +500 rewrites | unchanged, **0 rewrites** |
| After two | 3,013 modules / 4,678 rules / 447 KB; 344 MB cumulative text | unchanged |
| After destroying every editor | 3,013 modules still mounted | 15 |
| Create 500 editors, jsdom with CSS parse | 5,748 ms (451 ms for the first 50, 844–966 ms for the last 50s) | 2,583 ms (flat) |
| Reconfigure 500 editors, jsdom with CSS parse | 12,490 ms, then 19,094 ms | 738 ms, then 641 ms |
| Reconfigure 500 editors, CSS parse skipped | 852 ms, then 1,226 ms | 640 ms, then 486 ms |

Duplicate modules by text: `.underline {…}` ×1,500 and `.cm-error-line {…}`
×1,500 (after two reconfigures); every other module ×1.

### M3. Per-cell census with the real `<Cell>` (`census.test.tsx`)

`... vitest run --config ../.context/perf/frontend-editor-dom/vitest.config.mts census` → `census.json`.
Renders 2 and 22 cells of one kind, reports the per-cell delta (notebook-level
cost cancels out). Listener/observer/subscription counts are attributed by stack.

| Per cell | Hidden-code markdown + output | Code cell, no output |
| --- | --- | --- |
| Elements after React mount (skeleton placeholder) | 97 | 149 |
| Elements after editor build | 125 (33 are the invisible editor) | 246 in jsdom (157 CodeMirror, 24 of 31 lines drawn); ≈290 with all lines |
| Text nodes | 18 | 182 (≈235 with all lines) |
| Inline `<svg>` / their children | 12 / 27 | 10 / 27 |
| `button` / `[role=button]` | 15 | 13 |
| `.hover-action` elements | 5 | 6 |
| `[data-state]` elements (Radix) | 19 | 16 |
| jotai `store.sub` | 80 (73 React hooks + 7 CodeMirror plugins) | 77 |
| `document` `fullscreenchange` listeners | 11 | 10–11 |
| `document` `keydown` listeners (bubble) | 4 | 4–5 |
| `document` `keydown` listeners (capture, Radix Menu) | 3 | 3 |
| `document` `selectionchange` (CodeMirror) | 1 | 1 |
| `window` listeners | 7: `keydown`, `keyup`, `blur`, `mouseleave` (go-to-definition), `resize` ×2, `scroll`, `beforeprint` (CodeMirror) → 8 | 8 |
| Listeners on the editor's own DOM | 32 + **172 on `.cm-panel`** (a React root) | 32 |
| `IntersectionObserver` / `ResizeObserver` / `MutationObserver` constructed | 4 / 4 / 1 | 4 / 2 / 1 |
| CodeMirror style modules added | 2 | 2 (3 with the AI placeholder) |

Extrapolated to 500 cells (250 + 250): ≈104k elements + ≈63k text nodes; ≈43k
of the elements are per-cell chrome that is invisible until hover/focus; 5,500
inline SVGs; 7,000 buttons; ≈39k store subscriptions; ≈72k native event
listeners (43k of them on 250 hidden language-panel React roots); 13k listeners
on `window`/`document`.

A hidden markdown cell changes appearance when its editor is built (first cell,
before → after): editor wrapper `cm mo-code-placeholder opacity-20 h-8 …` →
`cm … h-0 overflow-hidden`; cell class gains `borderless`; tray `data-hidden`
`false` → `true`; output `style` unset → `max-height: none`.

### M4. Global event fan-out with real cells mounted (`events.test.tsx`)

`... vitest run --config … events` → `events.txt`. Half markdown / half code.

| Event | `window`+`document` callbacks per event | `addEventListener` calls made during dispatch | jsdom dispatch, 10 / 40 / 160 cells |
| --- | --- | --- | --- |
| `keydown` in an editor | **8 × cells** (1,280 at 160) | **6 × cells** (960 at 160) | 0.79 / 2.9 / **15.1 ms** (exponent 1.47 from 80→160) |
| `keyup` | 1 × cells | 0 | 0.13 / 0.30 / 0.52 ms |
| `selectionchange` | 1 × cells + 1 | 0 | 0.07 / 0.16 / 0.50 ms |
| `window` `resize` | 2 × cells | 0 | 0.11 / 0.22 / 1.05 ms |
| `window` `scroll` | 1 × cells | 0 | 0.05 / 0.12 / 0.71 ms |
| `fullscreenchange` | 10.5 × cells (1,681 at 160) | 0 | 0.43 / 2.1 / 10.9 ms |

At 500 cells one key press runs ≈4,000 global listener callbacks and makes
≈3,000 `document.addEventListener` calls.

### M5. Notebook-wide editor transactions (`variables.test.ts`)

| Trigger | 50 editors | 500 editors |
| --- | --- | --- |
| One keystroke in one editor | 4 dispatches | 4 dispatches (no fan-out) |
| `variablesAtom` replaced (a `variables` / `variable-values` message), smoke-shaped variables | 100 dispatches | **1,000 dispatches**, 29–93 ms inside `dispatch` in jsdom |
| same, 250 cross-cell variables | 100 | 1,000 dispatches, 30–137 ms |

### M6. Editor bundle (`extensions.test.tsx` → `extensions.txt`)

- `setupCodeMirror` returns 154 extension objects; 82 are shared singletons, **72 are constructed per cell**.
- Python editor: 26 view plugins, 91 facet/field slots, 110 key bindings from 11 keymap sources, 4 update listeners (+1 from `cell-editor.tsx`), 11 decoration sources, 14 style modules.
- Markdown editor: 30 view plugins, 97 slots, 120 key bindings, 5 update listeners (+1).
- `getExtension()` per call: python 0.001 ms, markdown 0.033 ms (39 objects, 21 new each call), sql 0.26 ms.
- Retained heap per `EditorState` without a view: ≈100 KB (≈50 MB for 500). With views in jsdom: ≈650 KB per editor (jsdom's DOM is JS heap, so this overstates a browser).

### M7. Markdown output rendering (`extensions.test.tsx` → `markdown-render.txt`)

250 real `mo.md` outputs (169–461 bytes each, 69 KB total), jsdom: DOMPurify 57.5 ms,
`html-react-parser` 3.4 ms, full `<HtmlOutput>` mount 115 ms for 1,336 elements,
re-render with identical props 0.68 ms.

### M8. Built CSS (`css-census.mjs`, `css-universal.mjs`)

`node .context/perf/frontend-editor-dom/css-census.mjs marimo/_static/assets/{index,cells,markdown-renderer,JsonOutput}-*.css`
Entry stylesheets: 402 KB, 3,561 rules, 4,106 selectors, 6,889 declarations, 82
`@property`, 26 `@font-face`. 25 `:has()` selectors, 85 `dark:` selectors of
the form `.x:is(.dark *):not(:where(.marimo.light,.marimo.light *))`, ≈110
selectors with no id/class/attribute/tag key in the rightmost compound (tested
against every element), 0 uses of `content-visibility`, 1 of `contain` (a
Tailwind utility), 0 `will-change`.

## Findings (highest impact first)

### F1. Two CodeMirror themes are defined per editor, so the editor stylesheet is rewritten 500 times, grows O(n), and never shrinks

- **Category:** `css-selectors`, `caching`, `algorithms`
- **Where:**
  - `frontend/src/core/codemirror/cells/traceback-decorations.ts:148` (`errorLineHighlighter` → `EditorView.theme({...})` on every call)
  - `frontend/src/core/codemirror/go-to-definition/extension.ts:15` (`goToDefinitionBundle` → `EditorView.baseTheme({...})` on every call)
  - same pattern, off by default or conditional: `placeholder/extensions.ts:135` (`clickablePlaceholderExtension`, active whenever AI is enabled; it also declares a new `WidgetType` class per call at line 69), `cells/debugger-decorations.ts:83` and `:180`, `cells/line-timing-decorations.ts:153`
  - all reached from `setupCodeMirror` (`core/codemirror/cm.ts:146`), called once per cell and again on every reconfigure (`components/editor/cell/code/cell-editor.tsx:202`)
  - mechanism: `@codemirror/view` `EditorView.mountStyles` (dist/index.js:8348, called from the constructor and at :8053 whenever the `styleModule` facet value changes) → `style-mod@4.1.3` `StyleSet.mount`, which for a document root does `this.styleTag.textContent = <all modules joined>` unconditionally and has no unmount.
- **Evidence:** MEASURED (M2). 2 new modules per editor; 1,013 modules / 1,678 rules / 157 KB after 500 editors; 499 whole-sheet rewrites and 42.5 MB of CSS text assigned during load; every notebook-wide reconfigure adds 1,000 more modules and 500 more rewrites; nothing is released when editors are destroyed, so the sheet grows for the life of the tab (cells created, deleted, reconfigured). In jsdom, per-editor creation cost doubles between the first and last 50 editors and reconfigure-all takes 12.5 s then 19.1 s. The cost *inside the browser's style engine* is INFERRED: each rewrite with new text replaces the active stylesheet, so Blink must re-parse a 13→157 KB sheet and run rule-set invalidation over the document, 500 times, interleaved with the progressive editor mount.
- **Why it is slow:** `EditorView.theme()`/`baseTheme()` return a fresh `StyleModule` each call; style-mod dedupes by object identity, so identical rules are appended once per editor, and each append rebuilds and reassigns the whole `<style>` text. Work per mount is O(modules so far) → O(n²) overall.
- **Proposed fix:** hoist the themes to module-level constants (as `codeLensTheme`, `highlightTheme`, `lightTheme` already are). Patch: `../patches/frontend-editor-dom-shared-codemirror-themes.patch` (applies cleanly; also hoists the go-to-definition `ViewPlugin`). Add a regression test asserting `setupCodeMirror` called twice yields identical `EditorView.styleModule` facet values.
- **Expected impact:** MEASURED with the prototype (M2): modules 1,013 → 15, sheet 157 KB → 12.9 KB (constant); creating 500 editors in jsdom 5.75 s → 2.58 s (−55%); reconfiguring 500 editors 12.5–19.1 s → 0.64–0.74 s (17–30×), with zero stylesheet rewrites on reconfigure. In a browser the remaining 499 rewrites carry identical text, which Blink serves from its stylesheet-contents cache.
- **Effort / risk:** S. Rules are unchanged; only their multiplicity changes. `baseTheme` vs `theme` precedence is preserved in the patch.

### F2. Every cell gets a full `EditorView`, including 268 editors that are never visible

- **Category:** `lazy-init`
- **Where:** `frontend/src/components/editor/cell/code/cell-editor.tsx:385-410` (every cell calls `editorMountScheduler.request`), `frontend/src/core/codemirror/editor-mount-scheduler.ts:58-71` (`processNext` drains the whole queue, one build per task; visibility only reorders it), `cell-editor.tsx:329-339` (`handleInitializeEditor`).
- **Evidence:** MEASURED (M1, M3, M4, M6). Building editors only for the 250 code cells takes 2,207 ms instead of 5,212 ms in jsdom (−58%). Each hidden markdown editor still costs: 33 DOM elements under an `h-0` wrapper; a separate React root for its language panel with **172 native listeners** (`core/codemirror/react-dom/createPanel.tsx:21`), re-rendered on every view update (`createPanel.tsx:28`); 30 view plugins; 7 store subscriptions; 1 `MutationObserver`, 2 `ResizeObserver`s, 2–3 `IntersectionObserver`s; 8 `window` + 1 `document` listeners; ≈100 KB of state. Every live editor also takes part in every `selectionchange` (5.9 ms per event at 500 in jsdom), `resize`, `scroll`, `keydown`/`keyup` and variables update (F7). A static highlighted `<pre>` for the same code costs 1.8 ms vs 5.6 ms for an editor in jsdom, and a plain `<pre>` 0.005 ms.
- **Why it is slow:** the scheduler makes construction non-blocking but not optional: total work is still 500 editors, and the steady-state cost of 500 live views (listeners, observers, plugin subscriptions, DOM) is paid forever.
- **Proposed fix:** make the editor demand-driven; the handles already tolerate a missing view (`editorViewOrNull`, `editorMountScheduler.promote` in `core/cells/cells.ts:637` and `scrollCellIntoView.ts:54`).
  1. Hidden-code cells whose output is shown (`hidden && hasOutput`): never enqueue. Build on `showHiddenCode`, focus, or `promote`.
  2. Other cells: build when within the `IntersectionObserver` margin that already exists (`cell-editor.tsx:433-446`) or on focus/promote; until then render static highlighted code (same lezer parser + `highlightTree`, as in the benchmark's `highlightedPre`) so text is readable and find-in-page works. Optionally destroy editors far off-screen (the serialized-state path at `cell-editor.tsx:361-378` already restores history/selection).
  3. Consumers of "all views" must fall back to the document: find/replace (`find-replace/search-highlight.ts:23,46`, `navigate.ts:40,115,157,204`), `getCodes` for Copilot, LSP document sync (`lsp/notebook-lsp.ts:91`), format-all, `useRunCells.ts:118`.
- **Expected impact:** step 1 alone: editor construction −58% (jsdom 5.2 s → 2.2 s), −8.8k DOM elements, −46k listeners, −268 React roots, −268 × 2 dispatches per variables update. Steps 1+2 for a first screen of ~10 cells: ~10 editors + 240 static blocks ≈ 0.5 s in jsdom (10×), and per-event fan-out (M4) drops from O(cells) to O(visible cells).
- **Effort / risk:** step 1 M, step 2 L. Risks: any feature that assumes `editorView` exists (list above), vim/search cross-cell navigation, scroll-height changes when a static block is swapped for an editor (needs identical line metrics), LSP diagnostics for un-built cells.

### F3. The language of a cell is unknown until its editor exists, so hidden markdown cells render wrong, then shift

- **Category:** `lazy-init`, `batching`
- **Where:** `frontend/src/components/editor/notebook-cell.tsx:410` (`useState<LanguageAdapterType>()` starts `undefined`), set only by the `ViewPlugin` at `cell-editor.tsx:263-275`; consumed at `notebook-cell.tsx:180-181` (`isMarkdownCodeHidden`), `:596-599` (`borderless`), `:567` (`forceExpand`), `:671` (`data-hidden`), and `cell-editor.tsx:450-457` (wrapper class).
- **Evidence:** MEASURED (M3, last paragraph): before its editor is built a hidden markdown cell shows a 32 px `h-8 opacity-20` skeleton strip, a border, and a height-limited output; afterwards the strip collapses to `h-0`, the border disappears and the output expands. Layout cost is INFERRED: 268 height changes, each moving everything below it, spread over the 500 scheduler tasks, plus one extra full re-render of each of the 500 cell components when `setLanguageAdapter` first fires.
- **Why it is slow:** presentation state is derived from an object that is deliberately created late.
- **Proposed fix:** initialise from the code: `useState(() => languageAdapterFromCode(cellData.code).type)` (3.4 ms for all 500 cells, M1), keep the plugin for later switches. Then the first render is already final and the skeleton for hidden cells is `h-0`.
- **Expected impact:** removes 268 layout shifts and 500 cell re-renders during load; prerequisite for F2 step 1 (a hidden markdown cell must render correctly with no editor at all).
- **Effort / risk:** S. `languageAdapterFromCode` must agree with what the editor later reports (it is the same function the editor uses at `cell-editor.tsx:337`).

### F4. Every key press runs ~4,000 global listeners and ~3,000 `addEventListener` calls

- **Category:** `dom-listeners`, `lazy-init`
- **Where:**
  - `@radix-ui/react-menu` `Menu` root effect (dist/index.mjs:67-80): a capture-phase `document` `keydown` listener per mounted menu, whose handler calls `document.addEventListener("pointerdown"|"pointermove", …, {capture, once})`. Three menus per cell are mounted while closed: two `CreateCellButton` dropdowns (`components/editor/cell/CreateCellButton.tsx:135`, rendered at `notebook-cell.tsx:856` and `:866`) and the context menu (`components/editor/cell/cell-context-menu.tsx:201`, wrapping every cell at `notebook-cell.tsx:629`).
  - `frontend/src/components/ui/button.tsx:131`: every `<Button>` registers a `document` `keydown` listener even when it has no `keyboardShortcut`; 4–5 per cell.
  - `frontend/src/core/codemirror/go-to-definition/underline.ts:66-69`: four `window` listeners per editor; on Meta/Ctrl every editor also adds `mousemove` and `click` listeners to its DOM (`:91-92`).
- **Evidence:** MEASURED (M3, M4): 8 callbacks and 6 `addEventListener` calls per cell per `keydown`; dispatch time in jsdom grows superlinearly (0.79 ms at 10 cells → 15.1 ms at 160). The superlinearity comes from the `addEventListener` duplicate check, a linear scan of same-type listeners on `document`; browsers do the same scan, with a smaller constant — the browser cost is INFERRED.
- **Why it is slow:** per-instance global listeners multiply by cell count, and one of them re-registers two more listeners on each key.
- **Proposed fix:**
  1. `button.tsx`: `useEventListener(keyboardShortcut ? document : null, …)`. Patch: `../patches/frontend-editor-dom-button-keydown-listener.patch`.
  2. Menus: mount on demand. One notebook-level `ContextMenu` that resolves the target cell from the event (`HTMLCellId.findElement`), and a `CreateCellButton` that renders a plain button and mounts its `DropdownMenu` only once opened (it already controls `open` itself).
  3. Go-to-definition: one module-level `window` listener tracking the modifier state, and attach `mousemove`/`click` only to the hovered/focused editor (or use `EditorView.domEventHandlers` and read `event.metaKey`).
- **Expected impact:** global callbacks per key press 8 × cells → ~0 × cells (4,000 → single digits at 500); `addEventListener` calls per key press 3,000 → 0; also removes 1,500 Radix menu roots and their `useCellActionButtons` work (F6).
- **Effort / risk:** 1 is S (no behaviour change). 2 is M (context-menu items depend on per-cell state; resolve lazily on open). 3 is S–M.

### F5. A settings or theme change rebuilds every editor's whole configuration

- **Category:** `batching`, `caching`
- **Where:** `cell-editor.tsx:202-327` (one `useMemo` over 28 dependencies builds the entire bundle), `:341-359` and `:412-417` (`StateEffect.reconfigure.of([extensions])` + language compartment for each cell). `core/codemirror/language/languages/markdown.ts:80` (`markdown()` built only to read `.language.data`), `:101-110` (a second `markdown({...})`, i.e. a second `parser.configure`), `:106` (`StreamLanguage.define(stexMath)` per call), `:117` (`python()` per call); `core/codemirror/language/extension.ts:60-63` (an `EditorState.create` per language switch to reset history).
- **Evidence:** MEASURED (M1): reconfiguring 500 editors takes 5,595 ms in jsdom — more than creating them — with exponent 1.52; 72 of 154 extension objects are rebuilt per cell (M6). Triggers, read from the dependency list (INFERRED frequency): any change of identity of `userConfig.keymap/completion/language_servers/display/diagnostics` (e.g. saving any setting if the config object is replaced wholesale), `theme`, `showPlaceholder`, AI enablement.
- **Why it is slow:** a full reconfigure makes CodeMirror re-resolve every facet and re-create every plugin for each view, and (until F1 is fixed) mount 1,000 new style modules.
- **Proposed fix:** F1 first (removes most of the measured cost). Then split the bundle: per-concern `Compartment`s (theme, keymap, completion/LSP, display) reconfigured individually; a module-level cache for cell-independent pieces (keymap arrays, language support per adapter + config); one shared markdown `LanguageSupport`. Skip reconfigure for editors that are not built (F2).
- **Expected impact:** with F1 alone 12.5 s → 0.7 s in jsdom with CSS parse (M2). Compartments would reduce a theme toggle to one facet change per editor.
- **Effort / risk:** M. Compartment state must survive language switches; easy to regress key-binding precedence (`core/codemirror/__tests__/setup.test.ts` snapshots it).

### F6. ~90 elements, 10–12 SVGs, ~75 store subscriptions and one AI chat client are mounted per cell for chrome that is hidden until hover

- **Category:** `lazy-init`, `dom-listeners`
- **Where:** `notebook-cell.tsx:627-778` (`EditableCellComponent` render) and children:
  - `components/editor/ai/ai-completion-editor.tsx:124,137` — a `DefaultChatTransport` and a `useChat` client per cell; `:252-268` — the "accept/reject" banner (switch, 3 buttons, 2 SVGs, ≈20 elements) is always rendered and hidden with `max-h-0 opacity-0`; wrappers use `transition-all`. `cell-editor.tsx:123` subscribes every cell to `aiCompletionCellAtom`, so opening the AI prompt in one cell re-renders all 500 `CellEditor`s.
  - `notebook-cell.tsx:827-876` `CellLeftSideActions`: two create-cell buttons, each a Radix `DropdownMenu` + `Tooltip`.
  - `notebook-cell.tsx:896-955` `CellToolbar`: run, stop, actions (`Popover` + `TooltipRoot`, `cell-actions.tsx:66` builds the full action list with icon elements on every render), and the same list is built again for the context menu (`cell-context-menu.tsx:61`).
  - `SortableCell.tsx:61,127-137` drag handle; `notebook-cell.tsx:723-738` delete button; `:549-559` collapse toggle; `Output.tsx:462-480` fullscreen button; `CellStatus.tsx` tooltips.
  - `components/ui/tooltip.tsx:16,73` + `components/ui/fullscreen.tsx:146,64`: every `Tooltip` mounts a portal wrapper that registers its own `document` `fullscreenchange` listener (F9).
  - `notebook-cell.tsx:628`: a `TooltipProvider` per cell.
  - `components/editor/cell/code/code-placeholder.tsx:24-46`: up to 101 elements of skeleton per cell, replaced a moment later.
- **Evidence:** MEASURED (M3): 84–89 non-editor, non-output elements per cell; 10–12 inline SVGs; 13–15 buttons; 16–19 Radix `data-state` nodes; 70–73 `store.sub` calls from React hooks per cell. At 500 cells: ≈43k chrome elements, 5,500 SVGs, ≈36k subscriptions. React mount cost per cell in jsdom was 15–40 ms (noisy).
- **Why it is slow:** DOM size and component count scale every full-tree operation (mount, style recalculation, layout, GC), and each hidden control carries hooks and subscriptions.
- **Proposed fix:** render the per-cell chrome only for the hovered/focused cell (one "active cell" slot driven by pointer-enter/focus-within, with the run button kept for `needs-run`); mount `AiCompletionEditor` only when `aiCompletionCell?.cellId === cellId` (select that boolean per cell instead of subscribing to the atom); share one `TooltipProvider`; replace the repeated lucide SVGs with a `<use>` sprite or CSS masks if the chrome stays mounted.
- **Expected impact:** ≈104k → ≈60k elements and ≈36k → <10k store subscriptions at 500 cells; 500 → 1 `useChat` clients; cell mount time roughly proportional (INFERRED).
- **Effort / risk:** M–L. Keyboard access to hidden controls (toolbar is reachable by focus today), layout stability when chrome appears, e2e selectors (`data-testid="run-button"` etc.).

### F7. Each variables message makes every editor re-analyse and dispatch twice, changed or not

- **Category:** `batching`, `algorithms`
- **Where:** `core/codemirror/reactive-references/extension.ts:62` (`store.sub(variablesAtom)` per editor), `:71` (also on every focus change), `:96` (dispatches even when ranges are unchanged/empty); `core/codemirror/code-lens/extension.ts:291-295` (four subscriptions per editor), `:351` (unconditional dispatch); `core/variables/state.ts:17-60` (every `setVariables`/`setMetadata` produces a new object, so subscribers always fire).
- **Evidence:** MEASURED (M5): 1,000 dispatches per message at 500 editors (2 per editor), 29–137 ms inside `dispatch` in jsdom, for both the smoke shape (no cross-cell variables, every result empty) and a 250-variable shape. Each dispatch runs all 26–30 view plugins and 5–6 update listeners of that editor, re-renders the language-panel React root of markdown editors (`createPanel.tsx:28`), and schedules a CodeMirror measure. The measure cost is INFERRED: `EditorView.measure` walks every ancestor calling `getComputedStyle` (`visiblePixelRange` in `@codemirror/view`), ~20 levels × 500 editors in one frame.
- **Why it is slow:** N independent subscriptions each do O(variables) + O(tree) work and an unconditional transaction.
- **Proposed fix:** compare before dispatching (skip when old and new ranges/lenses are both empty or equal — covers the whole smoke notebook); subscribe once at notebook level and fan out only to built, visible editors; markdown/SQL editors can skip both analyzers; drop `focusChanged` as a trigger.
- **Expected impact:** 1,000 → 0 dispatches per variables message for notebooks like the smoke test; O(visible) otherwise.
- **Effort / risk:** S for the equality check, M for the shared subscription. Go-to-definition reads `reactiveReferencesField.ranges`, so ranges must still refresh when an editor becomes visible.

### F8. `ConsoleOutput` reads layout in a dependency-less layout effect for every named cell

- **Category:** `dom-listeners`, `batching`
- **Where:** `frontend/src/components/editor/output/console/ConsoleOutput.tsx:134-149` (`useLayoutEffect` with no dependency array reads `scrollHeight`, `clientHeight`, `scrollTop`), `:86-94` (component not memoized), `:151` (the area is rendered for any cell with a non-default name even with no output — all 252 code cells of the notebook), rendered from `notebook-cell.tsx:751` with fresh closures each render.
- **Evidence:** INFERRED (code path verified; `console-output-area` is present in `sample-code-no-output.html` from M3). Every commit that re-renders a cell forces a synchronous layout in the commit phase. During a run each cell re-renders on queued → running → idle, so a 252-cell run-all performs on the order of 750 forced layouts between DOM mutations.
- **Why it is slow:** reading `scrollHeight` after React has mutated the DOM forces style + layout immediately instead of once per frame.
- **Proposed fix:** depend on `consoleOutputs` and return early when there are none; `memo` the component and stabilise `onClear`/`onRefactorWithAI` (`useEvent`); or drop the effect in favour of `overflow-anchor`/the existing `flex-col-reverse`.
- **Expected impact:** forced layouts during run-all ≈750 → number of cells that actually print.
- **Effort / risk:** S.

### F9. `useFullScreenElement` registers a `document` listener per tooltip/popover: ~5,250 at 500 cells

- **Category:** `dom-listeners`
- **Where:** `frontend/src/components/ui/fullscreen.tsx:60-68` (`useFullScreenElement` → `useEventListener(document, "fullscreenchange", …)`), used by `withFullScreenAsRoot` at `:146`, which wraps every `TooltipPortal` (`components/ui/tooltip.tsx:16`) and the popover/menu portals. The same file already has a shared subscription for `useIsFullScreen` (`:82-110`).
- **Evidence:** MEASURED (M3, M4): 10–11 listeners per cell; one `fullscreenchange` runs 10.5 callbacks per cell (10.9 ms at 160 cells in jsdom), each a `setState`.
- **Why it is slow:** per-instance global listener; on a fullscreen toggle thousands of components update at once.
- **Proposed fix:** implement `useFullScreenElement` with `useSyncExternalStore(subscribeToFullScreen, getFullScreenElement)`.
- **Expected impact:** 5,250 → 1 listener; mount/unmount of each tooltip no longer touches `document`.
- **Effort / risk:** S.

### F10. No containment on cells, and several selectors widen invalidation

- **Category:** `css-selectors`
- **Where and mechanism (all INFERRED — no style engine was run):**
  1. **No `contain` / `content-visibility` on `.marimo-cell` or `.output-area`** (`frontend/src/css/app/Cell.css:10-297`, `:484-495`; M8 finds 0 uses). Every style/layout/paint pass can reach all ~165k nodes. `content-visibility: auto` + `contain-intrinsic-size: auto <estimate>` on a per-cell wrapper lets Blink skip style, layout and paint for off-screen cells. Constraint: it implies paint containment, and cell chrome is positioned outside the cell box (`Cell.css:279-294` `.shoulder-right` at `left: calc(100% + 12px)`, `:392-407` `.tray::before/::after` gutters, `notebook-cell.tsx:851` `left-[-26px]`, `:674` `-top-4`; non-portalled tooltips in `cell/toolbar.tsx` and `cell/DeleteButton.tsx` use `usePortal={false}`), so it must go on an outer wrapper that includes the gutters, or the chrome must move inside.
  2. **Hover toggles `display` on 5–6 descendants per cell** (`frontend/src/css/common.css:7-9`, `:23-26`): moving the pointer across cells invalidates the `.hover-action` descendants of two cells and rebuilds their boxes (layout, not just paint). `visibility`/`opacity` would keep it to paint.
  3. **`.hover-actions-parent:has([data-state="open"]) .hover-action`** (`common.css:29-31`): the argument is an attribute Radix sets on 16–19 elements in every cell, so the fast-reject filter cannot exclude it; evaluating the rule walks the whole cell subtree (editor + output), and any `data-state` change inside a cell (a tooltip opening) re-evaluates it. Replace with a class/`data-menu-open` attribute set on the cell by the menu's `onOpenChange`.
  4. **`:root:has(body.dark)`** (`frontend/src/css/globals.css:135`): a `:has()` anchored on the root with a descendant argument makes the root "affected by `:has()`"; mutations that touch `:has`-relevant features can force the root to be re-evaluated, which scans the document for `body.dark`. Use `:root.dark`/set the class on `<html>`, or `html:has(> body.dark)` (child combinator bounds the scan to one level).
  5. `.marimo-cell.interactive .output-area:has(> .output:only-child > marimo-ui-element:only-child > marimo-table)` (`Cell.css:78-80`) is depth-bounded and cheap; listed for completeness. `div:has(> marimo-ui-element)` (`css/app/print.css:48`) is inside `@media print` and inert on screen.
  6. `.marimo-cell:hover`/`:focus-within` change `z-index` (`Cell.css:52-63`), and `.marimo-cell.focus-outline { transition: all 0.6s }` (`Cell.css:218-220`), `.marimo-output-stale { filter: grayscale(50%); transition: 300ms }` (`Cell.css:497-514`): during a run-all every cell's output gets a filter and a transition at once (one compositing layer per stale output while it animates).
  7. ≈110 universal-bucket selectors (`css-universal.txt`), notably `:root *`, `:is(.marimo,:root) *`, `.katex *`, Tailwind `space-*`/`divide-*` (`:where(.x>:not(:last-child))`), `.marimo-cell>:not(:last-child)` (from `@apply divide-y`, `Cell.css:17`) and ~70 `.prose… :where(h2+*)`-style typography rules. Each is tested against every element on a full recalculation; they matter only because full recalculations happen (F1) and the DOM is large (F2, F6).
  8. Class toggles on high ancestors that restyle the subtree: `#App.disconnected …` (`Cell.css:343-367`, on connection change), `body.dark`, `:root.marimo-fullscreen` (`common.css:34`). All rare.
- **Proposed fix:** items 1–4 above, in that order of value.
- **Expected impact:** not quantified here; item 1 is the only change that makes style/layout cost proportional to the visible cells rather than to the notebook. Needs the browser profile.
- **Effort / risk:** 2–4 are S. 1 is M (clipping of gutter chrome, sticky/absolute children, scroll-height estimates, CodeMirror measuring inside skipped subtrees).

### F11. Markdown editors each own a React root, and rebuild their language support per editor

- **Category:** `lazy-init`, `caching`
- **Where:** `core/codemirror/language/extension.ts:93-99` + `core/codemirror/react-dom/createPanel.tsx:19-36` (a `createRoot` per non-Python editor, `root.render` on every view update); `core/codemirror/language/languages/markdown.ts:80,97,101-110,117`; `core/codemirror/language/embedded/embedded-python.ts:121` (`extensions: [python().support]` per embedded range).
- **Evidence:** MEASURED: 172 listeners per panel root (M3); `getExtension` 0.033 ms and 21 new objects per call (M6) — the construction is cheap, the retained parsers/roots are the cost. Folded into F2 if hidden editors are not built.
- **Proposed fix:** render the panel lazily (on focus, or as a portal from the cell's existing React tree); cache one markdown `LanguageSupport`; read `markdownLanguage.data` directly instead of constructing `markdown()`.
- **Expected impact:** −43k listeners and −250 React roots at 500 cells even without F2.
- **Effort / risk:** S–M.

### F12. Plugin outputs: one shadow root, one React root and two `MutationObserver`s each

- **Category:** `lazy-init`, `dom-listeners`
- **Where:** `frontend/src/plugins/core/registerReactComponent.tsx:343-344` (shadow root + `copyStyles` in the constructor), `:371` (`createRoot`), `:378-383` (subtree `MutationObserver`), `:156` (attribute `MutationObserver`), `:546` (`adoptedStyleSheets`).
- **Evidence:** INFERRED (the smoke notebook has no plugin outputs; relevant for `outputs-N`). The stylesheet is *not* cloned per element — `styleSheetCache` (`:306`) shares one constructed sheet per source sheet — but every shadow root adopts the full 390 KB / 3.5k-rule app stylesheet, so each plugin is a separate style scope matched against all of it, plus ≈170 listeners for its React root.
- **Proposed fix:** defer mounting (`createRoot` + `copyStyles`) until the element is near the viewport; adopt a smaller "plugin" stylesheet.
- **Effort / risk:** M; flash of unstyled/empty plugins while scrolling.

## Ruled out

- **Language detection per cell.** 3.4 ms for 500 cells (M1); Python cells exit on `startsWith("mo.md(")`. Not parsed per keystroke except in `LanguageToggles` for the visible, edited cell.
- **Building the extension array.** 0.13 ms per cell (M1).
- **Highlight styles / themes created per cell.** `syntaxHighlighting(defaultHighlightStyle)`, `lightTheme`/`darkTheme`, code-lens and search themes are shared: 13 shared modules. Only the modules in F1 are per cell.
- **A keystroke dispatching into other editors.** 4 dispatches notebook-wide at both 50 and 500 editors (M5). The fan-out on typing is listeners (F4, F2), not transactions.
- **Markdown output rendering.** 115 ms for 250 outputs in jsdom, half of it DOMPurify; re-render with identical props 0.68 ms, so `memo` on `HtmlOutput`/`OutputRenderer` holds (M7). Paper cut only: `parseHtml` is not memoized (`plugins/core/RenderHTML.tsx:348`) and the sanitize memo depends on `shouldSanitizeHtml` even when `alwaysSanitizeHtml` is true (`:341-346`), so all markdown outputs re-sanitize once if that atom flips.
- **Non-passive scroll/wheel/touch listeners per cell.** None: CodeMirror's `wheel`, `touchstart`, `touchmove` are `passive: true` (M3 listener table).
- **`MutationObserver` on `document.body` with `subtree`.** None per cell; CodeMirror observes its own content element.
- **Scroll handlers.** One `scroll` listener per editor on `window` and on the scroller; non-intersecting editors return immediately (0.71 ms per event at 160 cells in jsdom).
- **Per-shadow-root stylesheet cloning.** Cached and shared (F12).
- **`resolveCodeMirrorTooltipParent`.** One `querySelector("#App")` per cell (`cm.ts:119`); negligible.
- **KaTeX CSS and fonts.** 381 selectors and 26 `@font-face` in the entry CSS (≈30 KB of 402 KB); class-keyed, fonts load on use. Bytes only.

## Could not measure

- Real style recalculation, layout, paint, compositing and memory. Everything about *how much* F1, F3, F8 and F10 cost in a browser is inferred from mechanism.
- Whether Blink limits invalidation when CodeMirror's `<style>` text is replaced with a longer sheet (F1), and the real cost of the `:has()` rules (F10).
- React render time per cell in a production build (jsdom + development React here).

## Benchmarks added

- `frontend/benchmarks/large-notebook-editor.bench.ts` — typed vitest bench, same style as `cell-analysis.bench.ts`. Run:
  `cd frontend && pnpm exec vitest bench benchmarks/large-notebook-editor.bench.ts --mode test --run --no-file-parallelism` (≈3 min; lint and `tsgo` clean).
- Proposed diffs (not applied; both pass `git apply --check`):
  `../patches/frontend-editor-dom-shared-codemirror-themes.patch`,
  `../patches/frontend-editor-dom-button-keydown-listener.patch`.
- Scratch probes in `.context/perf/frontend-editor-dom/` (not for commit). Run any with
  `cd frontend && pnpm exec vitest run --config ../.context/perf/frontend-editor-dom/vitest.config.mts <name>`:
  `style-growth` (env `REAL_STYLE=1`, `SHARE_THEMES=1`), `census`, `events`, `variables`, `extensions`.
  CSS: `node .context/perf/frontend-editor-dom/css-census.mjs <css…>`, `css-universal.mjs <css…>`.
  Outputs: `style-growth*.txt`, `census.json`, `sample-*.html`, `events.txt`, `variables.txt`, `extensions.txt`, `markdown-render.txt`, `css-census-main.txt`, `css-universal.txt`.
