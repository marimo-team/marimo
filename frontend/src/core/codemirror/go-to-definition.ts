/* Copyright 2024 Marimo. All rights reserved. */
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { getPositionAtWordBounds } from "../codemirror/completion/hints";
import { VariableName, Variables } from "../variables/types";
import { focusAndScrollCellIntoView } from "../cells/scrollCellIntoView";
import { store } from "../state/jotai";
import { notebookAtom } from "../cells/cells";
import { variablesAtom } from "../variables/state";

const getWordUnderCursor = (state: EditorState) => {
  const { from, to } = state.selection.main;
  let variableName: string;

  if (from === to) {
    const { startToken, endToken } = getPositionAtWordBounds(state.doc, from);
    variableName = state.doc.sliceString(startToken, endToken);
  } else {
    variableName = state.doc.sliceString(from, to);
  }

  return variableName;
};

const getCellIdOfDefinition = (variables: Variables, variableName: string) => {
  const variable = variables[variableName as VariableName];
  if (!variable || variable.declaredBy.length === 0) {
    return null;
  }
  const focusCellId = variable.declaredBy[0];
  return focusCellId;
};

export function goToDefinition(view: EditorView) {
  const state = view.state;
  const variables = store.get(variablesAtom);
  const variableName = getWordUnderCursor(state);
  const focusCellId = getCellIdOfDefinition(variables, variableName);

  if (focusCellId) {
    const notebookState = store.get(notebookAtom);
    focusAndScrollCellIntoView({
      cellId: focusCellId,
      cell: notebookState.cellHandles[focusCellId],
      config: notebookState.cellData[focusCellId].config,
      codeFocus: undefined,
      variableName,
    });
  }
}
