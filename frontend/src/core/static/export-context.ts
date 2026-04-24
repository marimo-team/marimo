/* Copyright 2026 Marimo. All rights reserved. */

import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { autoInstantiateAtom } from "@/core/config/config";
import { getInitialAppMode } from "@/core/mode";
import { store } from "@/core/state/jotai";

export interface MarimoExportContext {
  trusted: true;
  notebookCode?: string;
}

declare global {
  interface Window {
    __MARIMO_EXPORT_CONTEXT__?: Readonly<MarimoExportContext>;
  }
}

function isMarimoExportContext(
  value: unknown,
): value is Readonly<MarimoExportContext> {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as MarimoExportContext;
  if (candidate.trusted !== true) {
    return false;
  }
  if (
    candidate.notebookCode !== undefined &&
    typeof candidate.notebookCode !== "string"
  ) {
    return false;
  }
  return true;
}

export function getMarimoExportContext():
  | Readonly<MarimoExportContext>
  | undefined {
  const context = window?.__MARIMO_EXPORT_CONTEXT__;
  return isMarimoExportContext(context) ? context : undefined;
}

export function hasTrustedExportContext(): boolean {
  return getMarimoExportContext()?.trusted === true;
}

/**
 * True when the current page is a context where notebook-authored script
 * execution is expected, and therefore the user has consented (explicitly or
 * by the nature of the page) to running arbitrary notebook content:
 *
 * - the user has run at least one cell, OR
 * - a first-party exported notebook page installed a trusted export context
 *   (islands / static exports / Quarto islands), OR
 * - `auto_instantiate` is enabled (the notebook runs on page load by user
 *   configuration), OR
 * - the page was loaded in `read` / app mode (served by marimo as an app).
 *
 * Edit mode before any user interaction is intentionally NOT trusted — that
 * is the only surface where we must prevent notebook-authored content from
 * loading scripts or bypassing HTML sanitization.
 */
export function hasTrustedNotebookContext(): boolean {
  if (store.get(hasRunAnyCellAtom)) {
    return true;
  }
  if (hasTrustedExportContext()) {
    return true;
  }
  if (store.get(autoInstantiateAtom)) {
    return true;
  }
  try {
    if (getInitialAppMode() === "read") {
      return true;
    }
  } catch {
    // getInitialAppMode throws before mount config is applied; treat as untrusted.
  }
  return false;
}
