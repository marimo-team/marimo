/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "@/utils/Logger";
import { EditorView } from "@codemirror/view";

export function insertDebuggerAtLine(view: EditorView, line: number): boolean {
  // Get the document
  const { state } = view;
  const doc = state.doc;

  // Check if the line number is valid
  if (line <= 0 || line > doc.lines) {
    Logger.warn(
      `Invalid line number: ${line}. Document has ${doc.lines} lines.`,
    );
    return false;
  }

  // Get the target line
  const targetLine = doc.line(line);

  // Skip if line already contains breakpoint()
  if (targetLine.text.includes("breakpoint()")) {
    return true;
  }

  // Extract the indentation from the target line
  const lineContent = targetLine.text;
  const indentMatch = lineContent.match(/^(\s*)/);
  const indentation = indentMatch ? indentMatch[1] : "";

  // Create the breakpoint statement with the same indentation
  const breakpointStatement = `${indentation}breakpoint()\n`;

  // Get the position where we need to insert the breakpoint statement
  const insertPos = targetLine.from;

  // Create and dispatch the transaction
  view.dispatch({
    changes: {
      from: insertPos,
      to: insertPos,
      insert: breakpointStatement,
    },
  });

  // Scroll to the breakpoint
  view.dispatch({
    selection: {
      anchor: insertPos,
      head: insertPos,
    },
    scrollIntoView: true,
    effects: EditorView.scrollIntoView(insertPos, { y: "center" }),
  });

  return true;
}
