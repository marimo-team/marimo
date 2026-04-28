/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Resolve a cell's compiled-notebook outcome — predicted or actual.
 *
 * The Build panel and the dependency-graph "build status" mode both want
 * to talk about a cell's outcome in terms of one of a few stable labels
 * ({@link CellBuildKind}). The two source-of-truth shapes (the live
 * preview and the post-build cell results) carry richer state than the
 * UI needs, so funnel both through {@link cellBuildKind} which falls
 * back from "real build outcome" to "best static prediction" to
 * `undefined` (we have no opinion).
 */

import type { BuildPreviewCell, BuildState } from "@/core/build/atoms";
import type { CellId } from "@/core/cells/ids";

/**
 * The five compiled-notebook buckets the editor surfaces. ``compilable``
 * is a placeholder for "we know the cell is compilable but haven't run a
 * build yet" — it gets refined into ``loader``/``elided``/``verbatim``
 * after a build.
 */
export type CellBuildKind =
  | "loader"
  | "elided"
  | "verbatim"
  | "setup"
  | "compilable"
  | "non_compilable";

export function cellBuildKind(
  cellId: CellId,
  buildState: BuildState,
  preview: Map<CellId, BuildPreviewCell>,
): CellBuildKind | undefined {
  // Ground truth from a finished or in-flight build wins; the planner has
  // already collapsed `compiled`/`cached` into the loader bucket for us.
  const final = buildState.cellResults.get(cellId)?.final;
  if (final === "compiled" || final === "cached") {
    return "loader";
  }
  if (final === "elided") {
    return "elided";
  }
  if (final === "kept") {
    return "verbatim";
  }
  if (final === "setup") {
    return "setup";
  }

  const p = preview.get(cellId);
  if (!p) {
    return undefined;
  }
  if (p.confidence === "setup") {
    return "setup";
  }
  if (p.confidence === "non_compilable") {
    return "non_compilable";
  }
  if (p.predictedKind === "loader") {
    return "loader";
  }
  if (p.predictedKind === "elided") {
    return "elided";
  }
  if (p.predictedKind === "verbatim") {
    return "verbatim";
  }
  // Statically compilable but no prediction yet — useful so the graph
  // can hint "this cell *will* be classified once a build runs".
  if (p.confidence === "static" || p.confidence === "unmaterialized") {
    return "compilable";
  }
  return undefined;
}
