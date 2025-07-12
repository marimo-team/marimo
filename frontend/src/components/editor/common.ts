/* Copyright 2024 Marimo. All rights reserved. */

import type { CellId } from "@/core/cells/ids";
import { HTMLCellId } from "@/core/cells/ids";

/**
 * Create DOM properties for a cell.
 *
 * Returns:
 * - `data-cell-id` - The ID of the cell.
 * - `data-cell-name` - The name of the cell.
 * - `id` - The ID of the cell.
 */
export function cellDomProps(cellId: CellId, cellName: string) {
  return {
    "data-cell-id": cellId,
    "data-cell-name": cellName,
    id: HTMLCellId.create(cellId),
  };
}
