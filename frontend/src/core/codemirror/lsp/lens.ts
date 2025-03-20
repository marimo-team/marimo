/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import type * as LSP from "vscode-languageserver-protocol";

export interface NotebookLens {
  /** The ids of the cells in the notebook */
  cellIds: CellId[];

  /** The merged text of all cells in the notebook */
  mergedText: string;

  /** Transform a range from cell coordinates to notebook coordinates */
  transformRange: (range: LSP.Range, cellId: CellId) => LSP.Range;
  /** Transform a range from notebook coordinates back to cell coordinates */
  reverseRange: (range: LSP.Range, cellId: CellId) => LSP.Range;
  /** Transform a position from cell coordinates to notebook coordinates */
  transformPosition: (position: LSP.Position, cellId: CellId) => LSP.Position;
  /** Transform a position from notebook coordinates back to cell coordinates */
  reversePosition: (position: LSP.Position, cellId: CellId) => LSP.Position;

  /** Clip a range to the given cell */
  getEditsForNewText: (newText: string) => Array<{
    cellId: CellId;
    text: string;
  }>;

  /** Check if a range falls within the given cell */
  isInRange: (range: LSP.Range, cellId: CellId) => boolean;
}

/**
 * Basic utility for "zooming" a cell into the larger notebook context
 * and then "unzooming" ranges from the merged doc back to the original cell.
 */
export function createNotebookLens(
  sortedCellIds: CellId[],
  codes: Record<CellId, string>,
): NotebookLens {
  const cellLineOffsets = new Map<CellId, number>();

  // Calculate line offsets for each cell
  let currentOffset = 0;
  sortedCellIds.forEach((cellId) => {
    cellLineOffsets.set(cellId, currentOffset);
    currentOffset += codes[cellId].split("\n").length;
  });

  function getCurrentLineOffset(cellId: CellId): number {
    if (!cellLineOffsets.has(cellId)) {
      Logger.warn("[lsp] no cell line offsets for", cellId);
    }
    return cellLineOffsets.get(cellId) ?? 0;
  }

  const mergedText = Object.values(codes).join("\n");

  return {
    cellIds: sortedCellIds,

    mergedText,

    transformRange: (range: LSP.Range, cellId: CellId) =>
      shiftRange(range, getCurrentLineOffset(cellId)),

    reverseRange: (range: LSP.Range, cellId: CellId) =>
      shiftRange(range, -getCurrentLineOffset(cellId)),

    isInRange: (range: LSP.Range, cellId: CellId) => {
      const cellLines = codes[cellId].split("\n").length;
      const offset = cellLineOffsets.get(cellId) || 0;
      const startLine = range.start.line - offset;
      const endLine = range.end.line - offset;
      return startLine >= 0 && endLine < cellLines;
    },

    getEditsForNewText: (newText: string) => {
      const newLines = newText.split("\n");
      const oldLines = mergedText.split("\n");

      if (newLines.length !== oldLines.length) {
        throw new Error("Cannot apply rename when there are new lines");
      }

      const edits: Array<{
        cellId: CellId;
        text: string;
      }> = [];

      for (const [cellId, code] of Objects.entries(codes)) {
        if (!cellLineOffsets.has(cellId)) {
          continue;
        }
        const offset = cellLineOffsets.get(cellId) ?? 0;

        const numCellLines = code.split("\n").length;
        const newCellLines = newLines.slice(offset, offset + numCellLines);

        edits.push({
          cellId,
          text: newCellLines.join("\n"),
        });
      }

      return edits;
    },

    transformPosition: (position: LSP.Position, cellId: CellId) =>
      shiftPosition(position, getCurrentLineOffset(cellId)),

    reversePosition: (position: LSP.Position, cellId: CellId) =>
      shiftPosition(position, -getCurrentLineOffset(cellId)),
  };
}

function shiftRange(range: LSP.Range, offset: number): LSP.Range {
  return {
    start: shiftPosition(range.start, offset),
    end: shiftPosition(range.end, offset),
  };
}

function shiftPosition(position: LSP.Position, offset: number): LSP.Position {
  return {
    line: position.line + offset,
    character: position.character,
  };
}
