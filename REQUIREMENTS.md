# Chart Builder v2.0 — Requirements

The original ask: rebuild marimo's chart builder so it's pluggable, AI-friendly, scales to large datasets, and can persist into the notebook itself. Architecture, block contract, mutation pipeline, and PR breakdown live in [PLAN.md](PLAN.md).

## What we want

- **More chart types and richer controls.** Beyond today's six (bar, line, area, scatter, pie, heatmap): histogram, boxplot, candlestick, multi-y / dual-axis, plus deeper styling (axis format/scale/domain/ticks, font, mark style, data labels). Adding a new chart type should be one file plus its blocks — no edits to the orchestrator.
- **Pluggable backends for large datasets.** Today's in-browser Vega path stays the default; WASM VegaFusion (in-browser pre-aggregation) and Python VegaFusion (kernel-side pre-aggregation) slot in behind a `ChartBackend` interface so 50M-row charts render without UI changes.
- **Interactivity.** Brush / click / lasso selections become a `Predicate` IR that can be applied as a filter, used for drill-down, or broadcast as a cross-filter to sibling charts. The IR converts losslessly to SQL / pandas / polars / vega-lite predicates and is reusable outside charts.
- **AI-native via Vega-Lite.** Agents read and write Vega-Lite specs directly — no custom DSL. Smart defaults fire on every write; validation issues come with pre-baked auto-fixes that the agent applies with one call. Code-mode self-heals in Python via a small parity port (`marimo/_charts/`) without LLM round-trips or frontend RPCs.
- **`mo.chart_builder` as a persistent, source-authoritative output.** Parallel to `mo.md` / `mo.sql`: the cell source is the truth, UI edits write back to source, and the cell re-runs after a short debounce. Imports any Vega-Lite spec (e.g., `alt.Chart(df).mark_bar().encode(...).to_dict()`).
- **Vega-Lite as the canonical spec.** No second schema layer; the chart state IS a Vega-Lite spec. Builder-specific intent lives in `usermeta["marimo.chart_builder"]`. Any valid Vega-Lite spec round-trips losslessly — we render UI controls for a curated subset and pass everything else through verbatim.
- **One library, two consumers — staged delivery.** Both `mo.chart_builder` and the existing data-table chart builder should run on the same headless core. PR 1 ships `mo.chart_builder` only on the new library; the existing data-table chart builder stays on its current implementation until a later migration PR after `mo.chart_builder` reaches feature parity. The legacy path is feature-frozen in the interim.
- **Extensible by composition.** Chart types are pure composition of reusable blocks; adding a new block (a new facet style, axis control, tooltip mode) benefits every chart type for free. New chart types, backends, codegen targets, and AI artifacts ship as additive plugins — no edits to the orchestrator. The headless core has no React or DOM dependencies; lint-enforced module boundaries keep a future extraction to a standalone npm package mechanical (we keep it in the monorepo for now).

## Out of scope

- Real-time collaborative chart editing
- Publishing the library as a separate npm package (architecture is extraction-ready; no publish)
- An anywidget shell for `mo.chart_builder` (marimo-native plugin path ships first)
- Rendering anything other than Vega-Lite (codegen targets are pluggable; the canonical in-memory spec stays Vega-Lite)
- A full Python port of the TS core (only the executable subset — `validate`, `normalize`, `apply_ops`, `apply_fixes` — is ported)
- CompassQL-style chart recommendations (à la Voyager)
- A WYSIWYG canvas editor (drag-and-drop targets the sidebar and canvas drop zones; no draggable axes / annotations on the rendered chart itself)

See [PLAN.md](PLAN.md) for everything else.
