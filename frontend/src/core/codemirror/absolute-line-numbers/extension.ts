/* Copyright 2024 Marimo. All rights reserved. */

import type { Extension } from "@codemirror/state";
import { EditorView, lineNumbers } from "@codemirror/view";

/**
 * Creates a CodeMirror extension that displays absolute line numbers
 * based on the cell's position in the Python script file.
 *
 * @param lineOffset - The starting line number of the cell in the Python file (0-indexed)
 * @returns CodeMirror extension for absolute line numbers
 */
export function absoluteLineNumbers(lineOffset: number): Extension {
  return [
    lineNumbers({
      formatNumber: (lineNo: number) => {
        // lineNo is 1-indexed within the cell
        // lineOffset is the absolute starting line (0-indexed)
        // We want to display: lineOffset + lineNo
        return String(lineOffset + lineNo);
      },
    }),
    // Add a visual indicator class to the editor
    EditorView.editorAttributes.of({
      class: "cm-absolute-line-numbers",
    }),
  ];
}
