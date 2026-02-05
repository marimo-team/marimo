/* Copyright 2026 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";

export const DATA_CELL_ID = "data-cell-id";

export function getCellDomProps(cellId: string) {
  return {
    [DATA_CELL_ID]: cellId,
  };
}

export const DATA_FOR_CELL_ID = "data-for-cell-id";

export function getCellForDomProps(cellId: CellId) {
  return {
    [DATA_FOR_CELL_ID]: cellId,
  };
}
