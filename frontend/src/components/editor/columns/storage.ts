import type { CellColumnId } from "@/utils/id-tree";
import { ZodLocalStorage } from "@/utils/localStorage";
import { Logger } from "@/utils/Logger";
import { Paths } from "@/utils/paths";
import { z } from "zod";

const BASE_KEY = "marimo:notebook_col_sizes";

interface ColumnSizes {
  colToWidth: Record<CellColumnId, number>;
}

function initialState(): ColumnSizes {
  return { colToWidth: {} };
}

export const storage = new ZodLocalStorage<ColumnSizes>(
  getKey(),
  z.object({
    colToWidth: z.record(z.string(), z.number()),
  }),
  initialState,
);

function getKey() {
  const notebookPath = Paths.filenameWithDirectory();
  if (!notebookPath) {
    Logger.warn("No notebook path found");
    return BASE_KEY;
  }
  return `${BASE_KEY}:${notebookPath}`;
}

// Helper function to get width with default
export function getColumnWidth(
  columnId: CellColumnId,
): number | "contentWidth" {
  const width = storage.get().colToWidth[columnId];
  return width ?? "contentWidth";
}
