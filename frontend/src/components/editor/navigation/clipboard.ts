/* Copyright 2024 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { z } from "zod";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";

const MARIMO_CELL_MIMETYPE = "application/x-marimo-cell";

interface ClipboardCellData {
  cells: Array<{
    code: string;
  }>;
  version: "1.0";
}

const ClipboardCellDataSchema = z.object({
  cells: z.array(
    z.object({
      code: z.string(),
    }),
  ),
  version: z.literal("1.0"),
});

// NOTE: We don't support Cut yet. We can wait for feedback before implementing.
// It is a bit more complex as will need to:
// - include id, outputs, and name
// - delete the existing cell, but don't place on the undo stack
// - don't want to invalidate downstream cells

export function useCellClipboard() {
  const actions = useCellActions();

  const copyCells = useEvent(async (cellIds: CellId[]) => {
    const notebook = getNotebook();
    const cells = cellIds
      .map((cellId) => notebook.cellData[cellId])
      .filter(Boolean);

    if (cells.length === 0) {
      toast({
        title: "Error",
        description: "No cells found",
        variant: "danger",
      });
      return;
    }

    try {
      const clipboardData: ClipboardCellData = {
        cells: cells.map((cell) => ({
          code: cell.code,
        })),
        version: "1.0",
      };

      // Create plain text representation (joined by newlines)
      const plainText = cells.map((cell) => cell.code).join("\n\n");

      // Create clipboard item with both custom mimetype and plain text
      const clipboardItem = new ClipboardItem({
        [MARIMO_CELL_MIMETYPE]: new Blob([JSON.stringify(clipboardData)], {
          type: MARIMO_CELL_MIMETYPE,
        }),
        "text/plain": new Blob([plainText], {
          type: "text/plain",
        }),
      });

      await navigator.clipboard.write([clipboardItem]);

      const cellText = cells.length === 1 ? "Cell" : `${cells.length} cells`;
      toast({
        title: `${cellText} copied`,
        description: `${cellText} ${cells.length === 1 ? "has" : "have"} been copied to clipboard`,
      });
    } catch (error) {
      Logger.error("Failed to copy cells to clipboard", error);

      // Fallback to simple text copy
      try {
        const plainText = cells.map((cell) => cell.code).join("\n\n");
        await navigator.clipboard.writeText(plainText);
        const cellText = cells.length === 1 ? "Cell" : `${cells.length} cells`;
        toast({
          title: `${cellText} copied`,
          description: `${cellText} code ${cells.length === 1 ? "has" : "have"} been copied to clipboard`,
        });
      } catch {
        toast({
          title: "Copy failed",
          description: "Failed to copy cells to clipboard",
          variant: "danger",
        });
      }
    }
  });

  const pasteAtCell = useEvent(async (cellId: CellId) => {
    try {
      const clipboardItems = await navigator.clipboard.read();

      // Look for our custom mimetype first
      for (const item of clipboardItems) {
        if (item.types.includes(MARIMO_CELL_MIMETYPE)) {
          const blob = await item.getType(MARIMO_CELL_MIMETYPE);
          const text = await blob.text();

          try {
            const clipboardData = ClipboardCellDataSchema.parse(
              JSON.parse(text),
            );

            // If cells array is empty, fall through to plain text
            if (clipboardData.cells.length === 0) {
              break;
            }

            // Create new cells with the copied data after the current cell
            const currentCellId = cellId;
            for (const cell of clipboardData.cells) {
              actions.createNewCell({
                cellId: currentCellId,
                before: false,
                code: cell.code,
                autoFocus: false,
              });
              // Update currentCellId to the newly created cell for chaining
              // Note: We don't have the new cell ID here, but createNewCell handles the positioning
            }

            // Focus the last created cell
            if (clipboardData.cells.length > 0) {
              // The focus will be handled by the cell creation logic
            }

            return;
          } catch (parseError) {
            Logger.warn("Failed to parse clipboard cell data", parseError);
          }
        }
      }

      // Fallback to plain text
      const text = await navigator.clipboard.readText();
      if (text.trim()) {
        actions.createNewCell({
          cellId,
          before: false,
          code: text,
          autoFocus: true,
        });
      } else {
        toast({
          title: "Nothing to paste",
          description: "No cell or text found in clipboard",
          variant: "danger",
        });
      }
    } catch (error) {
      Logger.error("Failed to paste from clipboard", error);
      toast({
        title: "Paste failed",
        description: "Failed to read from clipboard",
        variant: "danger",
      });
    }
  });

  return {
    copyCells,
    pasteAtCell,
  };
}
