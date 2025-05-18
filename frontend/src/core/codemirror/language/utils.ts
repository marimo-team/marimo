/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import type { EditorState } from "@codemirror/state";
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
  const doc = editor.state.doc;
  // Noop if the code is the same
  if (doc.toString() === code) {
    return code;
  }
  editor.dispatch({
    changes: { from: 0, to: doc.length, insert: code },
  });
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
