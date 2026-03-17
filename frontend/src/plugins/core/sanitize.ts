/* Copyright 2026 Marimo. All rights reserved. */
import { atom, useAtomValue } from "jotai";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { autoInstantiateAtom } from "@/core/config/config";
import { getInitialAppMode } from "@/core/mode";

// Re-export so existing consumers don't break.
export { sanitizeHtml } from "./sanitize-html";

/**
 * Whether to sanitize the html.
 * When running as an app or with auto_instantiate enabled
 * we ignore sanitization because they should be treated as a website.
 */
const sanitizeHtmlAtom = atom<boolean>((get) => {
  const hasRunAnyCell = get(hasRunAnyCellAtom);
  const autoInstantiate = get(autoInstantiateAtom);

  // If a user has specifically run at least one cell or auto_instantiate is enabled, we don't need to sanitize.
  // HTML needs to be rich to allow for interactive widgets and other dynamic content.
  if (hasRunAnyCell || autoInstantiate) {
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
