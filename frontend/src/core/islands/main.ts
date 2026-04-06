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

/**
 * Main entry point for the js bundle for embedded marimo apps.
 */
export async function initialize() {
  await initializeIslands({ bridge: getGlobalBridge() });
}

// Auto-initialize on module load
void initialize().catch((error) => {
  Logger.error("Failed to initialize islands:", error);
});
