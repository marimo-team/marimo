/* Copyright 2024 Marimo. All rights reserved. */

import { closeCompletion } from "@codemirror/autocomplete";
import type { EditorState } from "@codemirror/state";
import { closeHoverTooltips, type EditorView } from "@codemirror/view";
import type { CellId } from "@/core/cells/ids";
import { notebookAtom } from "../../cells/cells";
import { store } from "../../state/jotai";
import { variablesAtom } from "../../variables/state";
import type { VariableName, Variables } from "../../variables/types";
import { getPositionAtWordBounds } from "../completion/hints";
import { goToLine, goToVariableDefinition } from "./commands";

/**
 * Get the word under the cursor.
 */
function getWordUnderCursor(state: EditorState) {
  const { from, to } = state.selection.main;
  if (from === to) {
    const { startToken, endToken } = getPositionAtWordBounds(state.doc, from);
    return state.doc.sliceString(startToken, endToken);
  }

  return state.doc.sliceString(from, to);
}

/**
 * Get the cell id of the definition of the given variable.
 */
function getCellIdOfDefinition(
  variables: Variables,
  variableName: string,
): CellId | null {
  if (!variableName) {
    return null;
  }
  const variable = variables[variableName as VariableName];
  if (!variable || variable.declaredBy.length === 0) {
    return null;
  }
  return variable.declaredBy[0];
}

function isPrivateVariable(variableName: string) {
  return variableName.startsWith("_");
}

/**
 * Go to the definition of the variable under the cursor.
 * @param view The editor view at which the command was invoked.
 */
export function goToDefinitionAtCursorPosition(view: EditorView): boolean {
  const { state } = view;
  const variableName = getWordUnderCursor(state);
  if (!variableName) {
    return false;
  }
  // Close popovers/tooltips
  closeCompletion(view);
  view.dispatch({ effects: closeHoverTooltips });

  return goToDefinition(view, variableName);
}

/**
 * Go to the definition of the variable under the cursor.
 * @param view The editor view at which the command was invoked.
 */
export function goToDefinition(
  view: EditorView,
  variableName: string,
): boolean {
  // The variable may exist in another cell
  const editorWithVariable = getEditorForVariable(view, variableName);
  if (!editorWithVariable) {
    return false;
  }
  return goToVariableDefinition(editorWithVariable, variableName);
}

/**
 * Go to the given line number in the cell with the given ID.
 * @param cellId The ID of the cell to go to.
 * @param line The line number to go to.
 */
export function goToCellLine(cellId: CellId, lineNumber: number): boolean {
  const view = getEditorForCell(cellId);
  if (!view) {
    return false;
  }
  return goToLine(view, lineNumber);
}

/**
 * @param editor The editor view at which the command was invoked.
 * @param variableName  The name of the variable to go to.
 */
function getEditorForVariable(
  editor: EditorView,
  variableName: string,
): EditorView | null {
  // If it's a private variable, we only want to go to the
  // definition if it's in the same cell
  if (isPrivateVariable(variableName)) {
    return editor;
  }

  const variables = store.get(variablesAtom);

  const cellId = getCellIdOfDefinition(variables, variableName);
  if (cellId) {
    return getEditorForCell(cellId);
  }

  return null;
}

/**
 * Go to the given line number in the editor view.
 * @param view The editor view to go to.
 * @param line The line number to go to.
 */
function getEditorForCell(cellId: CellId): EditorView | null {
  const notebookState = store.get(notebookAtom);
  return notebookState.cellHandles[cellId].current?.editorView ?? null;
}
