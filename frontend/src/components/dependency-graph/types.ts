/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";

export type LayoutDirection = "TB" | "LR";
export type GraphLayoutView = LayoutDirection | "_minimap_";

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
}
