/* Copyright 2024 Marimo. All rights reserved. */

import { z } from "zod";
import { arrayMove } from "@/utils/arrays";
import { NotebookScopedLocalStorage } from "@/utils/localStorage";

const BASE_KEY = "marimo:notebook-col-sizes";

interface ColumnSizes {
  widths: Array<number | "contentWidth">;
}

function initialState(): ColumnSizes {
  return { widths: [] };
}

const storage = new NotebookScopedLocalStorage<ColumnSizes>(
  BASE_KEY,
  z.object({
    widths: z.array(
      z.union([z.number(), z.literal("contentWidth")]).default("contentWidth"),
    ),
  }),
  initialState,
);

export const storageFn = {
  // Default to "contentWidth" if the column width is not set.
  getColumnWidth: (index: number) => {
    const widths = storage.get(BASE_KEY).widths;
    return widths[index] ?? "contentWidth";
  },
  saveColumnWidth: (index: number, width: number | "contentWidth") => {
    const widths = storage.get(BASE_KEY).widths;
    if (widths[index]) {
      widths[index] = width;
    } else {
      // If the index is out of bounds, add "contentWidth" until we reach the index
      while (widths.length <= index) {
        widths.push("contentWidth");
      }
      widths[index] = width;
    }
    storage.set(BASE_KEY, { widths });
  },
  clearStorage: () => {
    storage.remove(BASE_KEY);
  },
};

// When a column is reordered, we need to update the storage to reflect the new order.
export function reorderColumnSizes(fromIdx: number, toIdx: number) {
  const widths = storage.get(BASE_KEY).widths;
  const newWidths = arrayMove(widths, fromIdx, toIdx);
  storage.set(BASE_KEY, { widths: newWidths });
}
