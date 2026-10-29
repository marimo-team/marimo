/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorState } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { getCellCode } from "./cell-code";
import { languageAdapterState } from "./extension";
import { languageMetadataField } from "./metadata";

/**
 * Get the editor code as Python
 * Handles when the editor has a different language adapter
 */
export function getEditorCodeAsPython(
  editor: { state: EditorState },
  fromPos?: number,
  toPos?: number,
): string {
  if (fromPos === undefined) {
    return getCellCode(editor.state);
  }
  const languageAdapter = editor.state.field(languageAdapterState);
  const metadata = editor.state.field(languageMetadataField);
  const editorText = editor.state.doc.toString();
  return languageAdapter.transformOut(
    editorText.slice(fromPos, toPos),
    metadata,
  )[0];
}

/**
 * Split the editor code into two parts at the cursor position
 */
export function splitEditor(editor: EditorView) {
  const cursorPos = editor.state.selection.main.head;
  const editorCode = editor.state.doc.toString();

  const isCursorAtLineStart =
    editorCode.length > 0 && editorCode[cursorPos - 1] === "\n";
  const isCursorAtLineEnd =
    editorCode.length > 0 && editorCode[cursorPos] === "\n";

  const beforeAdjustedCursorPos = isCursorAtLineStart
    ? cursorPos - 1
    : cursorPos;
  const afterAdjustedCursorPos = isCursorAtLineEnd ? cursorPos + 1 : cursorPos;

  const beforeCursorCode = getEditorCodeAsPython(
    editor,
    0,
    beforeAdjustedCursorPos,
  );
  const afterCursorCode = getEditorCodeAsPython(editor, afterAdjustedCursorPos);

  return {
    beforeCursorCode,
    afterCursorCode,
  };
}
