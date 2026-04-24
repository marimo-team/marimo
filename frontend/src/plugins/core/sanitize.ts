/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useAtomValue } from "jotai";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { autoInstantiateAtom } from "@/core/config/config";
import { getInitialAppMode } from "@/core/mode";
import { hasTrustedExportContext } from "@/core/static/export-context";

// Re-export so existing consumers don't break.
export { sanitizeHtml } from "./sanitize-html";

/**
 * Whether to sanitize the html. Trust signals match
 * `hasTrustedNotebookContext` in `@/core/static/export-context`.
 * Kept as a jotai atom so consumers re-render when `hasRunAnyCellAtom`
 * flips after the user runs a cell.
 */
const sanitizeHtmlAtom = atom<boolean>((get) => {
  const hasRunAnyCell = get(hasRunAnyCellAtom);
  const autoInstantiate = get(autoInstantiateAtom);

  if (hasRunAnyCell || autoInstantiate) {
    return false;
  }

  // Trusted export context is installed once at page load by a first-party
  // script (frozen + non-configurable), so a direct read is safe and stable.
  if (hasTrustedExportContext()) {
    return false;
  }

  let isInAppMode = true;
  try {
    isInAppMode = getInitialAppMode() === "read";
  } catch {
    // If it fails to get the initial app mode, we default to sanitizing.
    return true;
  }

  // Apps need to run javascript and load external resources.
  if (isInAppMode) {
    return false;
  }

  return true;
});

/**
 * Whether to sanitize the html.
 */
export function useSanitizeHtml() {
  return useAtomValue(sanitizeHtmlAtom);
}
