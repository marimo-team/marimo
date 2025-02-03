/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "@/utils/Logger";
import type * as LSP from "vscode-languageserver-protocol";

/**
 * Basic utility for "zooming" a cell into the larger notebook context
 * and then "unzooming" ranges from the merged doc back to the original cell.
 */
export function createNotebookLens(cell: string, allCode: string[]) {
  // Track how many lines come before the cell by finding cell index
  const cellIndex = allCode.indexOf(cell);
  const lineOffset = allCode
    .slice(0, cellIndex)
    .reduce((count, c) => count + c.split("\n").length, 0);

  if (cellIndex === -1) {
    Logger.warn("Cell not found in allCode", { cell, allCode });

    return {
      mergedText: cell,
      transformRange: (range: LSP.Range) => range,
      reverseRange: (range: LSP.Range) => range,
      isInRange: (range: LSP.Range) => true,
      transformPosition: (position: LSP.Position) => position,
      reversePosition: (position: LSP.Position) => position,
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

  return {
    mergedText: allCode.join("\n"),

    /**
     * Convert a cell-based range into the merged document. (Not currently invoked,
     * but would be useful if you want to intercept LSP requests and shift them to
     * the notebook-wide doc.)
     */
    transformRange: (range: LSP.Range) => shiftRange(range, lineOffset),

    /**
     * Adjust incoming LSP ranges from the merged doc back to the original cell's line offsets.
     * This is useful for mapping e.g. hover ranges or diagnostic ranges into local cell space.
     */
    reverseRange: (range: LSP.Range) => shiftRange(range, -lineOffset),

    isInRange: (range: LSP.Range) => {
      const cellLines = cell.split("\n").length;
      const startLine = range.start.line;
      const endLine = range.end.line;
      return startLine >= 0 && endLine < cellLines;
    },

    /**
     * Convert a cell-based position into the merged document.
     */
    transformPosition: (position: LSP.Position) =>
      shiftPosition(position, lineOffset),

    /**
     * Adjust incoming LSP position from the merged doc back to the original cell's line offset.
     */
    reversePosition: (position: LSP.Position) =>
      shiftPosition(position, -lineOffset),
  };
}
