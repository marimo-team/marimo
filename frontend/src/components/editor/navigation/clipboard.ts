/* Copyright 2024 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { z } from "zod";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";

const MARIMO_CELL_MIMETYPE = "application/x-marimo-cell";

interface ClipboardCellData {
  code: string;
  version: "1.0";
}

const ClipboardCellDataSchema = z.object({
  code: z.string(),
  version: z.literal("1.0"),
});

// NOTE: We don't support Cut yet. We can wait for feedback before implementing.
// It is a bit more complex as will need to:
// - include id, outputs, and name
// - delete the existing cell, but don't place on the undo stack
// - don't want to invalidate downstream cells

export function useCellClipboard() {
  const actions = useCellActions();

  const copyCell = useEvent(async (cellId: CellId) => {
    const cellData = getNotebook().cellData[cellId];
    if (!cellData) {
      toast({
        title: "Error",
        description: "Cell not found",
        variant: "danger",
      });
      return;
    }

    try {
      const clipboardData: ClipboardCellData = {
        code: cellData.code,
        version: "1.0",
      };

      // Create clipboard item with both custom mimetype and plain text
      const clipboardItem = new ClipboardItem({
        [MARIMO_CELL_MIMETYPE]: new Blob([JSON.stringify(clipboardData)], {
          type: MARIMO_CELL_MIMETYPE,
        }),
        "text/plain": new Blob([cellData.code], {
          type: "text/plain",
        }),
      });

      await navigator.clipboard.write([clipboardItem]);

      toast({
        title: "Cell copied",
        description: "Cell has been copied to clipboard",
      });
    } catch (error) {
      Logger.error("Failed to copy cell to clipboard", error);

      // Fallback to simple text copy
      try {
        await navigator.clipboard.writeText(cellData.code);
        toast({
          title: "Cell copied",
          description: "Cell code has been copied to clipboard",
        });
      } catch {
        toast({
          title: "Copy failed",
          description: "Failed to copy cell to clipboard",
          variant: "danger",
        });
      }
    }
  });

  const pasteCell = useEvent(async (cellId: CellId) => {
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

            // Create a new cell with the copied data after the current cell
            // We don't use name or config yet, as it may not be desired or make sense to copy over as well.
            actions.createNewCell({
              cellId,
              before: false,
              code: clipboardData.code,
              autoFocus: true,
            });
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
    copyCell,
    pasteCell,
  };
}
