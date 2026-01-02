/* Copyright 2026 Marimo. All rights reserved. */

import type { TransactionSpec } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { suppressSignatureHelp } from "@marimo-team/codemirror-languageserver";

/**
 * Replace the entire content of the editor with new content.
 *
 * When the editor has focus, this function attempts to preserve the cursor position
 * by keeping it on the same line and column. If the line no longer exists or shrinks,
 * the cursor is adjusted accordingly. This prevents the cursor from jumping during
 * external updates (e.g., auto-formatting or external edits).
 *
 * When the editor doesn't have focus, the content is replaced without any special handling.
 *
 * @param editor - The CodeMirror editor view
 * @param newContent - The new content to replace the editor with
 * @param options - Optional configuration
 * @param options.preserveCursor - Whether to preserve cursor position when focused (default: true)
 * @param options.effects - Additional effects to apply to the transaction
 * @param options.userEvent - User event string for the transaction
 */
export function replaceEditorContent(
  editor: EditorView,
  newContent: string,
  options: {
    preserveCursor?: boolean;
    effects?: TransactionSpec["effects"];
    userEvent?: string;
  } = {},
): void {
  const { preserveCursor = true, effects, userEvent } = options;
  const doc = editor.state.doc;
  const currentContent = doc.toString();

  // Noop if content is the same
  if (currentContent === newContent) {
    return;
  }

  // If editor has focus and we want to preserve cursor, try to maintain position
  if (preserveCursor && editor.hasFocus) {
    const cursorPos = editor.state.selection.main.head;

    // Get the current line and column
    const currentLine = doc.lineAt(cursorPos);
    const lineNumber = currentLine.number; // 1-based line number
    const columnInLine = cursorPos - currentLine.from; // 0-based column in line

    // Calculate new cursor position based on line-aware logic
    const newDoc = editor.state.update({
      changes: { from: 0, to: doc.length, insert: newContent },
    }).state.doc;

    let newCursorPos: number;

    if (lineNumber <= newDoc.lines) {
      // Line still exists in new document
      const newLine = newDoc.line(lineNumber);
      const newLineLength = newLine.length;

      // Keep same column, but clamp to line length if line shrank
      newCursorPos = newLine.from + Math.min(columnInLine, newLineLength);
    } else {
      // Line no longer exists, move to the end of the last line
      const lastLine = newDoc.line(newDoc.lines);
      newCursorPos = lastLine.to;
    }

    // Apply changes with preserved cursor position
    editor.dispatch({
      changes: { from: 0, to: doc.length, insert: newContent },
      annotations: suppressSignatureHelp.of(true), // External edits should not show signature help
      selection: {
        anchor: newCursorPos,
      },
      effects,
      userEvent,
    });
  } else {
    // Editor doesn't have focus or we don't want to preserve cursor
    editor.dispatch({
      changes: { from: 0, to: doc.length, insert: newContent },
      effects,
      userEvent,
    });
  }
}
