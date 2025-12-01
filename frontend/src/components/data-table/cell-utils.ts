/* Copyright 2024 Marimo. All rights reserved. */

export const DATA_CELL_ID = "data-cell-id";

export function getCellDomProps(cellId: string) {
  return {
    [DATA_CELL_ID]: cellId,
  };
}
