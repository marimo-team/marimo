/* Copyright 2026 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";

export type LayoutDirection = "TB" | "LR";

export type GraphSelection =
  | {
      type: "node";
      id: CellId;
    }
  | {
      type: "edge";
      source: CellId;
      target: CellId;
    }
  | undefined;

export interface GraphSettings {
  hidePureMarkdown: boolean;
  hideReusableFunctions: boolean;
  /**
   * Recolor nodes by their compiled-notebook outcome
   * (loader / elided / verbatim) — predicted from the live preview, or
   * exact when a build has run.
   */
  showBuildStatus: boolean;
  /** Hide cells that would be removed from the compiled notebook. */
  hideElidedCells: boolean;
  /** Hide cells that compile to an artifact loader. */
  hideCompiledCells: boolean;
}
