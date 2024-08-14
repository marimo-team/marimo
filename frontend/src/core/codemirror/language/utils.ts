/* Copyright 2024 Marimo. All rights reserved. */
import type { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";
import type { EditorState } from "@codemirror/state";

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
  const editorText = editor.state.doc.toString();
  if (fromPos !== undefined) {
    return languageAdapter.transformOut(editorText.slice(fromPos, toPos))[0];
  }
  return languageAdapter.transformOut(editorText)[0];
}

/**
 * Update the editor code from Python code
 * Handles when the editor is showing a different language (e.g. markdown)
 */
export function updateEditorCodeFromPython(
  editor: EditorView,
  pythonCode: string,
) {
  const languageAdapter = editor.state.field(languageAdapterState);
  const [code] = languageAdapter.transformIn(pythonCode);
  editor.dispatch({
    changes: {
      from: 0,
      to: editor.state.doc.length,
      insert: code,
    },
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

export function unsplitEditors(
  firstEditor: EditorView,
  secondEditor: EditorView,
) {
  // TODO: Undo new line splits here
  const cellCode = firstEditor.state.doc.toString();
  const newCellCode = secondEditor.state.doc.toString();
  return cellCode + newCellCode;
}
