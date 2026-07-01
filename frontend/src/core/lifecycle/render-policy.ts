/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { hasCellsAtom, notebookAtom } from "../cells/cells";
import { isOutputEmpty } from "../cells/outputs";
import { KnownQueryParams } from "../constants";
import { showCodeInRunModeAtom } from "../meta/state";
import { type AppMode, initialModeAtom } from "../mode";
import { hasQueryParam } from "@/utils/urls";

export interface RenderPolicy {
  /** False in `present` mode, and in `read` mode when the user has opted to hide code. */
  showCode: boolean;
  /** True only when there are real, non-empty cached outputs to display. */
  showCachedOutputs: boolean;
  /**
   * Whether the current view has anything to paint without waiting on the
   * runtime:
   * - In edit/home/gallery mode, this is `hasCells` — the editor renders the
   *   cell skeleton even when output is empty.
   * - In read/present mode with code visible, the cell source is enough.
   * - In headless read mode (code hidden), we need either cached outputs or a
   *   settled notebook (all cells idle) — a completed but output-less notebook
   *   is still "done" and shouldn't strand on an infinite spinner.
   */
  canPaint: boolean;
}

function readCodeVisibility(
  mode: AppMode | undefined,
  showAppCode: boolean,
): boolean {
  if (mode === "edit" || mode === "home" || mode === "gallery") {
    return true;
  }
  if (mode === "present") {
    return false;
  }
  // read mode (or undefined). If `marimo run` stripped the sources
  // (`--include-code` off), there is no code to show regardless of any other
  // signal — mirror `core/meta/code-visibility.ts` so the two don't drift.
  if (hasQueryParam(KnownQueryParams.includeCode, "false")) {
    return false;
  }
  // Otherwise the URL `show-code` param wins, then the view config.
  if (hasQueryParam(KnownQueryParams.showCode, "false")) {
    return false;
  }
  if (hasQueryParam(KnownQueryParams.showCode, "true")) {
    return true;
  }
  return showAppCode;
}

function computeRenderPolicy(input: {
  mode: AppMode | undefined;
  showAppCode: boolean;
  hasCells: boolean;
  hasCachedOutputs: boolean;
  /**
   * True when every cell is idle. A settled notebook is paintable even with no
   * visible outputs — otherwise a completed but output-less notebook viewed in
   * headless read mode would strand on an infinite spinner. Mirrors the
   * pre-framework `hasAnyOutputAtom` idle fallback.
   */
  allCellsIdle: boolean;
}): RenderPolicy {
  const showCode = readCodeVisibility(input.mode, input.showAppCode);
  const showCachedOutputs = input.hasCells && input.hasCachedOutputs;
  const canPaint =
    input.hasCells && (showCode || showCachedOutputs || input.allCellsIdle);

  return { showCode, showCachedOutputs, canPaint };
}

/**
 * Both cell-runtime facts the render policy needs, computed in a single pass
 * over `cellRuntime`:
 * - `hasCachedOutputs`: any cell has a non-empty output.
 * - `allCellsIdle`: every cell's status is idle — nothing queued or running.
 *   Vacuously true for an empty notebook, so `canPaint` still gates on
 *   `hasCells`.
 *
 * Fan out to two boolean selector atoms below so `renderPolicyAtom` only
 * recomputes when one of the booleans actually flips, not on every notebook
 * update.
 */
const cellRuntimeSummaryAtom = atom((get) => {
  let hasCachedOutputs = false;
  let allCellsIdle = true;
  for (const runtime of Object.values(get(notebookAtom).cellRuntime)) {
    if (!isOutputEmpty(runtime.output)) {
      hasCachedOutputs = true;
    }
    if (runtime.status !== "idle") {
      allCellsIdle = false;
    }
  }
  return { hasCachedOutputs, allCellsIdle };
});

const hasCachedOutputsAtom = atom(
  (get) => get(cellRuntimeSummaryAtom).hasCachedOutputs,
);

const allCellsIdleAtom = atom(
  (get) => get(cellRuntimeSummaryAtom).allCellsIdle,
);

export const renderPolicyAtom = atom<RenderPolicy>((get) =>
  computeRenderPolicy({
    mode: get(initialModeAtom),
    showAppCode: get(showCodeInRunModeAtom),
    hasCells: get(hasCellsAtom),
    hasCachedOutputs: get(hasCachedOutputsAtom),
    allCellsIdle: get(allCellsIdleAtom),
  }),
);

/** Sugar over `renderPolicyAtom.canPaint`. */
export const canPaintAtom = atom((get) => get(renderPolicyAtom).canPaint);

export const visibleForTesting = {
  computeRenderPolicy,
};
