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

/** Returns whether the current document can replace its app in this worker. */
export function canReplaceApp(): boolean {
  if (!document.querySelector(ISLAND_TAG_NAMES.ISLAND)) {
    return false;
  }
  return parseMarimoIslandApps(document, { materialize: false }).length === 1;
}

/**
 * Mounts marimo custom elements and starts the apps in the current document.
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

/** Stops the matching active app session. */
export async function stopApp(appId?: string): Promise<void> {
  await bridge.stopSession(appId);
}

// Auto-initialize on module load
void initialize().catch((error) => {
  Logger.error("Failed to initialize islands:", error);
});
