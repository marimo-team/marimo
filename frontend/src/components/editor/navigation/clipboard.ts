/* Copyright 2026 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { z } from "zod";
import { toast } from "@/components/ui/use-toast";
import { getNotebook, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import {
  usePendingCutActions,
  usePendingCutState,
} from "@/core/cells/pending-cut-service";
import type { CellConfig } from "@/core/network/types";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";

// According to MDN, custom mimetypes should start with "web "
const MARIMO_CELL_MIMETYPE = "web application/x-marimo-cell";

export interface ClipboardCellData {
  cells: {
    code: string;
    name?: string;
    config?: CellConfig;
  }[];
  version: "1.0";
}

const ClipboardCellDataSchema = z.object({
  cells: z.array(
    z.object({
      code: z.string(),
      name: z.string().optional(),
      config: z
        .object({
          column: z.union([z.number(), z.null()]).optional(),
          disabled: z.boolean().optional(),
          hide_code: z.boolean().optional(),
        })
        .optional(),
    }),
  ),
  version: z.literal("1.0"),
});

export function useCellClipboard() {
  const actions = useCellActions();
  const pendingCutActions = usePendingCutActions();
  const pendingCutState = usePendingCutState();

  const copyCells = useEvent(async (cellIds: CellId[]) => {
    const notebook = getNotebook();
    const cells = cellIds
      .map((cellId) => notebook.cellData[cellId])
      .filter(Boolean);

    if (cells.length === 0) {
      // No cells to copy
      return;
    }

    try {
      const clipboardData: ClipboardCellData = {
        cells: cells.map((cell) => ({
          code: cell.code,
          name: cell.name,
          config: cell.config,
        })),
        version: "1.0",
      };

      // Create plain text representation (joined by newlines)
      const plainText = cells.map((cell) => cell.code).join("\n\n");

      // Create clipboard item with both custom mimetype and plain text
      const clipboardItem = new ClipboardItemBuilder()
        .add(MARIMO_CELL_MIMETYPE, clipboardData)
        .add("text/plain", plainText)
        .build();

      await navigator.clipboard.write([clipboardItem]);

      toastSuccess(cells.length);
    } catch (error) {
      Logger.error("Failed to copy cells to clipboard", error);

      // Fallback to simple text copy
      try {
        const plainText = cells.map((cell) => cell.code).join("\n\n");
        await copyToClipboard(plainText);
        toastSuccess(cells.length);
      } catch {
        toastError();
      }
    }
  });

  const cutCells = useEvent(async (cellIds: CellId[]) => {
    const notebook = getNotebook();
    const cells = cellIds
      .map((cellId) => notebook.cellData[cellId])
      .filter(Boolean);

    if (cells.length === 0) {
      // No cells to cut
      return;
    }

    try {
      const clipboardData: ClipboardCellData = {
        cells: cells.map((cell) => ({
          code: cell.code,
          name: cell.name,
          config: cell.config,
        })),
        version: "1.0",
      };

      // Create plain text representation (joined by newlines)
      const plainText = cells.map((cell) => cell.code).join("\n\n");

      // Create clipboard item with both custom mimetype and plain text
      const clipboardItem = new ClipboardItemBuilder()
        .add(MARIMO_CELL_MIMETYPE, clipboardData)
        .add("text/plain", plainText)
        .build();

      await navigator.clipboard.write([clipboardItem]);

      // Mark cells as pending cut instead of deleting immediately
      pendingCutActions.markForCut({ cellIds, clipboardData });
      toastCutSuccess(cells.length);
    } catch (error) {
      Logger.error("Failed to cut cells to clipboard", error);

      // Fallback to simple text copy
      try {
        const clipboardData: ClipboardCellData = {
          cells: cells.map((cell) => ({
            code: cell.code,
            name: cell.name,
            config: cell.config,
          })),
          version: "1.0",
        };
        const plainText = cells.map((cell) => cell.code).join("\n\n");
        await copyToClipboard(plainText);
        // Mark cells as pending cut instead of deleting immediately
        pendingCutActions.markForCut({ cellIds, clipboardData });
        toastCutSuccess(cells.length);
      } catch {
        toastError();
      }
    }
  });

  interface PasteOptions {
    before?: boolean;
  }

  const pasteAtCell = useEvent(async (cellId: CellId, opts?: PasteOptions) => {
    const { before = false } = opts ?? {};

    // Check if we have pending cut cells (internal move)
    if (pendingCutState.cellIds.size > 0) {
      const pendingCellIds = [...pendingCutState.cellIds];

      actions.moveCellsRelativeTo({
        cellIds: pendingCellIds,
        targetCellId: cellId,
        position: before ? "before" : "after",
      });

      pendingCutActions.clear();
      toastPasteSuccess(pendingCellIds.length);
      return;
    }

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

            // Create new cells with the copied data before/after the current cell
            const currentCellId = cellId;
            const reversedCells = [...clipboardData.cells].reverse();
            for (const cell of reversedCells) {
              actions.createNewCell({
                cellId: currentCellId,
                before,
                code: cell.code,
                name: cell.name,
                config: cell.config,
                autoFocus: true,
              });
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
          before,
          code: text,
          autoFocus: true,
        });
      } else {
        toastNothingToPaste();
      }
    } catch (error) {
      Logger.error("Failed to paste from clipboard", error);
      toastPasteFailed();
    }
  });

  return {
    copyCells,
    cutCells,
    pasteAtCell,
    clearPendingCut: pendingCutActions.clear,
  };
}

const toastSuccess = (cellLength: number) => {
  const cellText = cellLength === 1 ? "Cell" : `${cellLength} cells`;
  toast({
    title: `${cellText} copied`,
    description: `${cellText} ${cellLength === 1 ? "has" : "have"} been copied to clipboard.`,
  });
};

const toastCutSuccess = (cellLength: number) => {
  const cellText = cellLength === 1 ? "Cell" : `${cellLength} cells`;
  toast({
    title: `${cellText} marked for cut`,
    description: `${cellText} will be moved on paste.`,
  });
};

const toastPasteSuccess = (cellLength: number) => {
  const cellText = cellLength === 1 ? "Cell" : `${cellLength} cells`;
  toast({
    title: `${cellText} moved`,
    description: `${cellText} ${cellLength === 1 ? "has" : "have"} been moved.`,
  });
};

const toastError = () => {
  toast({
    title: "Copy failed",
    description: "Failed to copy cells to clipboard.",
    variant: "danger",
  });
};

const toastNothingToPaste = () => {
  toast({
    title: "Nothing to paste",
    description: "No cell or text found in clipboard.",
    variant: "danger",
  });
};

const toastPasteFailed = () => {
  toast({
    title: "Paste failed",
    description: "Failed to read from clipboard",
    variant: "danger",
  });
};

class ClipboardItemBuilder {
  private items: Record<string, string | Blob> = {};

  add(mimeType: string, value: string | object) {
    // Skip if the browser doesn't support the mime type
    if (!ClipboardItem.supports(mimeType)) {
      Logger.warn(`ClipboardItem does not support ${mimeType}`);
      return this;
    }

    if (typeof value === "string") {
      this.items[mimeType] = new Blob([value], { type: mimeType });
      return this;
    }

    this.items[mimeType] = new Blob([JSON.stringify(value)], {
      type: mimeType,
    });
    return this;
  }

  build() {
    return new ClipboardItem(this.items);
  }
}
