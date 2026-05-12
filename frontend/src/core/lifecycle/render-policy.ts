/* Copyright 2026 Marimo. All rights reserved. */

import { atom } from "jotai";
import { hasCellsAtom, notebookAtom } from "../cells/cells";
import { isOutputEmpty } from "../cells/outputs";
import { KnownQueryParams } from "../constants";
import { showCodeInRunModeAtom } from "../meta/state";
import { type AppMode, initialModeAtom } from "../mode";

export interface RenderPolicy {
  /** False in `present` mode, and in `read` mode when the user has opted to hide code. */
  showCode: boolean;
  showCachedOutputs: boolean;
  /**
   * Whether the current view has anything to paint without waiting on the
   * runtime:
   * - In edit/home/gallery mode, this is `hasCells` — the editor renders the
   *   cell skeleton even when output is empty.
   * - In read/present mode with code visible, the cell source is enough.
   * - In headless read mode (code hidden), we need cached outputs to display.
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
  // read mode (or undefined): URL param wins, then view config.
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    if (params.get(KnownQueryParams.showCode) === "false") {
      return false;
    }
    if (params.get(KnownQueryParams.showCode) === "true") {
      return true;
    }
  }
  return showAppCode;
}

/** Exposed for unit tests; production reads go through `renderPolicyAtom`. */
export function computeRenderPolicy(input: {
  mode: AppMode | undefined;
  showAppCode: boolean;
  hasCells: boolean;
  hasCachedOutputs: boolean;
}): RenderPolicy {
  const showCode = readCodeVisibility(input.mode, input.showAppCode);
  const showCachedOutputs = input.hasCells && input.hasCachedOutputs;
  const canPaint = input.hasCells && (showCode || showCachedOutputs);

  return { showCode, showCachedOutputs, canPaint };
}

const hasCachedOutputsAtom = atom<boolean>((get) => {
  const runtimeStates = Object.values(get(notebookAtom).cellRuntime);
  return runtimeStates.some((runtime) => !isOutputEmpty(runtime.output));
});

export const renderPolicyAtom = atom<RenderPolicy>((get) =>
  computeRenderPolicy({
    mode: get(initialModeAtom),
    showAppCode: get(showCodeInRunModeAtom),
    hasCells: get(hasCellsAtom),
    hasCachedOutputs: get(hasCachedOutputsAtom),
  }),
);

/** Sugar over `renderPolicyAtom.canPaint`. */
export const canPaintAtom = atom((get) => get(renderPolicyAtom).canPaint);
