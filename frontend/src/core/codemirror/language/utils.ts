/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorState } from "@codemirror/state";
import type { EditorView } from "@codemirror/view";
import { replaceEditorContent } from "../replace-editor-content";
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
  const languageAdapter = editor.state.field(languageAdapterState);
  const metadata = editor.state.field(languageMetadataField);
  const editorText = editor.state.doc.toString();
  if (fromPos !== undefined) {
    return languageAdapter.transformOut(
      editorText.slice(fromPos, toPos),
      metadata,
    )[0];
  }
  return languageAdapter.transformOut(editorText, metadata)[0];
}

/**
 * Update the editor code from Python code
 * Handles when the editor is showing a different language (e.g. markdown)
 */
export function updateEditorCodeFromPython(
  editor: EditorView,
  pythonCode: string,
): string {
  const languageAdapter = editor.state.field(languageAdapterState);
  const [code] = languageAdapter.transformIn(pythonCode);
  // Use replaceEditorContent which preserves cursor position when focused
  replaceEditorContent(editor, code);
  return code;
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
