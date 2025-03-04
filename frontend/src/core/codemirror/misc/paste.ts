/* Copyright 2024 Marimo. All rights reserved. */
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { movementCallbacksState } from "../config/extension";

export function pasteBundle(): Extension[] {
  return [
    EditorView.domEventHandlers({
      paste: (event: ClipboardEvent, view: EditorView) => {
        const text = event.clipboardData?.getData("text/plain");
        if (!text?.includes("@app.cell")) {
          return false;
        }

        const cells = extractCells(text);
        if (cells.length === 0) {
          return false;
        }

        const movementCallbacks = view.state.facet(movementCallbacksState);
        movementCallbacks.createManyBelow(cells);
        return true;
      },
    }),
  ];
}

/**
 * Extract the cells from a marimo app.
 */
export function extractCells(text: string): string[] {
  // Quick check if this looks like a marimo app
  if (!text.includes("@app.cell")) {
    return [];
  }

  const cells: string[] = [];
  const lines = text.split("\n");
  let currentCell: string[] = [];
  let inCell = false;
  let skipLines = 0;
  let inMultilineArgs = false;
  let inMultilineReturn = false;
  let parenCount = 0;

  // Pre-compile regex patterns
  const leadingParenRegex = /\(/g;
  const trailingParenRegex = /\)/g;
  const cellEndMarkers = new Set(["@"]);

  function countParens(line: string): number {
    return (
      (line.match(leadingParenRegex) || []).length -
      (line.match(trailingParenRegex) || []).length
    );
  }

  function finalizeCellIfNeeded() {
    if (currentCell.length === 0) {
      return;
    }

    // Remove trailing returns
    while (
      currentCell.length > 0 &&
      currentCell[currentCell.length - 1].trim().startsWith("return")
    ) {
      currentCell.pop();
    }

    // Only add non-empty cells
    if (currentCell.some((l) => l.trim() !== "")) {
      cells.push(dedent(currentCell.join("\n")));
    }
    currentCell = [];
  }

  for (const line of lines) {
    const trimmed = line.trim();

    // Skip empty lines between cells
    if (!trimmed && !inCell) {
      continue;
    }

    // Start of a new cell
    if (trimmed.startsWith("@app.cell")) {
      finalizeCellIfNeeded();
      inCell = true;
      skipLines = 1; // Skip the def line
      continue;
    }

    // Handle function definition and args
    if (skipLines > 0) {
      if (
        trimmed.startsWith("def") &&
        trimmed.includes("(") &&
        !trimmed.includes("):")
      ) {
        inMultilineArgs = true;
        parenCount = countParens(trimmed);
      }
      skipLines--;
      continue;
    }

    // Track multi-line arguments
    if (inMultilineArgs) {
      parenCount += countParens(trimmed);
      if (parenCount === 0) {
        inMultilineArgs = false;
      }
      continue;
    }

    if (!inCell) {
      continue;
    }

    // Handle cell content
    if (cellEndMarkers.has(trimmed[0]) || trimmed.startsWith("if __name__")) {
      finalizeCellIfNeeded();
      inCell = trimmed.startsWith("@");
      continue;
    }

    // Handle return statements
    if (trimmed.startsWith("return")) {
      if (trimmed.includes("(") && !trimmed.endsWith(")")) {
        inMultilineReturn = true;
        parenCount = countParens(trimmed);
      }
      continue;
    }

    if (inMultilineReturn) {
      parenCount += countParens(trimmed);
      if (parenCount === 0) {
        inMultilineReturn = false;
      }
      continue;
    }

    // Add line to current cell
    currentCell.push(line);
  }

  // Handle last cell
  finalizeCellIfNeeded();

  return cells;
}

function dedent(text: string): string {
  const lines = text.split("\n");
  if (lines.length === 0) {
    return "";
  }

  // Cache non-empty lines
  const nonEmptyLines = lines.filter((line) => line.trim().length > 0);
  if (nonEmptyLines.length === 0) {
    return "";
  }

  const leadingSpaceRegex = /^\s*/;
  const minIndent = Math.min(
    ...nonEmptyLines.map(
      (line) =>
        leadingSpaceRegex.exec(line)?.[0].length ?? Number.POSITIVE_INFINITY,
    ),
  );

  return minIndent === 0
    ? text.trim()
    : lines
        .map((line) => line.slice(minIndent))
        .join("\n")
        .trim();
}
