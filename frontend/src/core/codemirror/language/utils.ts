/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";

/**
 * Get the editor code as Python
 * Handles when the editor has a different language adapter
 */
export function getEditorCodeAsPython(
  editor: EditorView,
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
