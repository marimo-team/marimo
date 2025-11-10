/* Copyright 2024 Marimo. All rights reserved. */
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

import { IslandsBootstrap } from "./bootstrap";
import { getGlobalBridge } from "./bridge";

/**
 * Main entry point for the js bundle for embedded marimo apps.
 */

/**
 * Initialize the Marimo app.
 *
 * @deprecated Use IslandsBootstrap class directly for better testability
 */
export async function initialize() {
  const bootstrap = new IslandsBootstrap({
    bridge: getGlobalBridge(),
  });
  await bootstrap.initialize();
}

// Auto-initialize on module load
initialize();
