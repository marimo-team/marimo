/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { languageAdapterState } from "./extension";

/**
 * Get the editor code as Python
 * Handles when the editor has a different language adapter
 */
export function getEditorCodeAsPython(editor: EditorView): string {
  const languageAdapter = editor.state.field(languageAdapterState);
  return languageAdapter.transformOut(editor.state.doc.toString())[0];
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
