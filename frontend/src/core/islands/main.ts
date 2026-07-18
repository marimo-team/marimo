/* Copyright 2026 Marimo. All rights reserved. */
import "./islands.css";
import "../../css/common.css";
import "../../css/globals.css";
import "../../css/codehilite.css";
import "../../css/katex.min.css";
import "../../css/md.css";
import "../../css/admonition.css";
import "../../css/md-tooltip.css";
import "../../css/table.css";

import "iconify-icon";

import { Logger } from "@/utils/Logger";
import { initializeIslands } from "./bootstrap";
import { getGlobalBridge } from "./bridge";
import { ISLAND_CSS_CLASSES, ISLAND_TAG_NAMES } from "./constants";
import { parseMarimoIslandApps } from "./parse";

const bridge = getGlobalBridge();
let bootstrapPromise: Promise<void> | undefined;

/**
 * Public entry point for the islands bundle.
 *
 * Islands auto-initialize on load. Hosts that keep the browser realm alive
 * across client-side navigation (retaining this worker and its Pyodide
 * environment) can drive page transitions with:
 *
 * ```ts
 * if (canReplaceApp()) {
 *   await stopApp();
 *   updatePage();
 *   await initialize();
 * }
 * ```
 *
 * The retained lifecycle (`canReplaceApp`/`stopApp`) only applies to pages
 * whose islands resolve to a single app; multi-app pages are not replaceable.
 */

/**
 * Returns whether the current document can replace its app in this worker.
 *
 * True only when the document contains exactly one replaceable app. This is a
 * read-only probe: it does not materialize island payloads or mutate the DOM.
 */
export function canReplaceApp(): boolean {
  if (!document.querySelector(ISLAND_TAG_NAMES.ISLAND)) {
    return false;
  }
  return parseMarimoIslandApps(document, { materialize: false }).length === 1;
}

/**
 * Mounts marimo custom elements and starts the apps in the current document.
 *
 * Safe to call repeatedly, including after client-side navigation: the worker
 * bootstrap is memoized (and cleared if it fails, so a later call retries),
 * while app discovery re-runs on every call to pick up the current DOM.
 */
export async function initialize(): Promise<void> {
  const islands = document.querySelectorAll<HTMLElement>(
    ISLAND_TAG_NAMES.ISLAND,
  );
  if (islands.length === 0) {
    return;
  }
  for (const island of islands) {
    island.classList.add(ISLAND_CSS_CLASSES.NAMESPACE);
  }
  bootstrapPromise ??= initializeIslands({ bridge }).catch((error: unknown) => {
    bootstrapPromise = undefined;
    throw error;
  });
  await bootstrapPromise;
  await bridge.initializeApps();
}

/**
 * Stops the matching active app session.
 *
 * With no `appId`, stops the current retained single-app session; with an
 * `appId`, stops it only if it matches the active app. No-op when there is no
 * retained session to stop.
 */
export async function stopApp(appId?: string): Promise<void> {
  await bridge.stopSession(appId);
}

// Auto-initialize on module load
void initialize().catch((error) => {
  Logger.error("Failed to initialize islands:", error);
});
