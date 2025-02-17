/* Copyright 2024 Marimo. All rights reserved. */
import { yCollab } from "y-codemirror.next";
import type { CellId } from "@/core/cells/ids";
import { isWasm } from "@/core/wasm/utils";
import type { Extension } from "@codemirror/state";
import { CellProviderManager } from "./cell-manager";

export function realTimeCollaboration(
  cellId: CellId,
  initialCode = "",
): { extension: Extension; code: string } {
  if (isWasm()) {
    return {
      extension: [],
      code: initialCode,
    };
  }

  const manager = CellProviderManager.getInstance();
  const { ytext } = manager.getOrCreateProvider(cellId, initialCode);

  const extension = yCollab(ytext, null);

  return {
    code: ytext.toJSON(),
    extension,
  };
}
