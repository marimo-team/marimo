/* Copyright 2026 Marimo. All rights reserved. */

import { closeCompletion } from "@codemirror/autocomplete";
import { syntaxTree } from "@codemirror/language";
import { Facet, type EditorState } from "@codemirror/state";
import {
  closeHoverTooltips,
  type EditorView,
  type KeyBinding,
  keymap,
} from "@codemirror/view";
import type { CellId } from "@/core/cells/ids";
import { PyNode } from "../python-node-names";
import { hotkeysAtom, platformAtom } from "../../config/config";
import { notebookAtom } from "../../cells/cells";
import { store } from "../../state/jotai";
import { variablesAtom } from "../../variables/state";
import type { VariableName, Variables } from "../../variables/types";
import { getPositionAtWordBounds } from "../completion/hints";
import {
  findVariableDefinitionPosition,
  goToLine,
  goToPosition,
} from "./commands";

function keymapBindingMatchesHotkey(
  binding: KeyBinding,
  hotkey: string,
): boolean {
  const platform = store.get(platformAtom);
  const bindingKey =
    platform === "mac"
      ? (binding.mac ?? binding.key)
      : platform === "windows"
        ? (binding.win ?? binding.key)
        : (binding.linux ?? binding.key);
  return bindingKey === hotkey;
}

/**
 * Get the word under the cursor.
 */
function getWordUnderCursor(state: EditorState) {
  const { from, to } = state.selection.main;
  if (from === to) {
    const { startToken, endToken } = getPositionAtWordBounds(state.doc, from);
    return {
      position: startToken,
      word: state.doc.sliceString(startToken, endToken),
    };
  }

  return {
    position: from,
    word: state.doc.sliceString(from, to),
  };
}

interface IdentifierAtPosition {
  canResolveLocally: boolean;
  position: number;
  word: string;
}

/** Get an exact Python identifier at the given document position. */
function getIdentifierAtPosition(
  state: EditorState,
  pos: number,
): IdentifierAtPosition | null {
  const node = syntaxTree(state).resolveInner(pos, 1);
  if (node.name !== PyNode.VariableName && node.name !== PyNode.PropertyName) {
    return null;
  }

  return {
    canResolveLocally: node.name === PyNode.VariableName,
    position: node.from,
    word: state.doc.sliceString(node.from, node.to),
  };
}

/** Whether this editor can ask a language server for a definition. */
export const lspGoToDefinitionSupport = Facet.define<boolean, boolean>({
  combine: (values) => values.some(Boolean),
});

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
  const { position, word } = getWordUnderCursor(view.state);
  return goToWord(view, word, position);
}

/** Tagged keymap handler so LSP fallback can skip marimo's local resolver. */
export const marimoGoToDefinitionKeymap = function run(
  view: EditorView,
): boolean {
  return goToDefinitionAtCursorPosition(view);
};

/**
 * Go to the definition of the variable at the given document position.
 *
 * Unlike {@link goToDefinitionAtCursorPosition}, this resolves the word at an
 * explicit position (e.g. where the user right-clicked) rather than the
 * current text cursor.
 * @param view The editor view at which the command was invoked.
 * @param pos The document position to resolve the word from.
 */
export function goToDefinitionAtPosition(
  view: EditorView,
  pos: number,
): boolean {
  const identifier = getIdentifierAtPosition(view.state, pos);
  if (!identifier?.canResolveLocally) {
    return false;
  }
  const { position, word } = identifier;
  return goToWord(view, word, position);
}

/**
 * Go to the definition at an explicit position, falling back to the language
 * server after moving the caret to the selected identifier.
 */
export function goToDefinitionAtPositionWithLspFallback(
  view: EditorView,
  pos: number,
): boolean {
  const identifier = getIdentifierAtPosition(view.state, pos);
  if (!identifier) {
    return false;
  }
  if (
    identifier.canResolveLocally &&
    goToWord(view, identifier.word, identifier.position)
  ) {
    return true;
  }

  view.dispatch({
    selection: {
      anchor: identifier.position,
      head: identifier.position,
    },
  });
  return requestLspGoToDefinition(view);
}

/**
 * Whether to offer "Go to Definition" at the given document position.
 * The position must be an exact Python variable token with either a definition
 * marimo can resolve synchronously or an available language-server fallback.
 * @param view The editor view at which the command was invoked.
 * @param pos The document position to resolve the word from.
 */
export function canRequestDefinitionAtPosition(
  view: EditorView,
  pos: number,
): boolean {
  const identifier = getIdentifierAtPosition(view.state, pos);
  if (!identifier) {
    return false;
  }
  return (
    view.state.facet(lspGoToDefinitionSupport) ||
    (identifier.canResolveLocally &&
      resolveDefinition(view, identifier.word, identifier.position) != null)
  );
}

/**
 * Close open popovers and navigate to the definition of the given word.
 * Returns `false` (a no-op) when there is no word.
 */
function goToWord(view: EditorView, word: string, position: number): boolean {
  if (!word) {
    return false;
  }
  // Close popovers/tooltips
  closeCompletion(view);
  view.dispatch({ effects: closeHoverTooltips });

  return goToDefinition(view, word, position);
}

/**
 * Invoke the editor's go-to-definition keymap handlers for the configured
 * hotkey. Matches CodeMirror key strings directly (including customized
 * shortcuts like `Ctrl-F12`) instead of synthesizing keyboard events.
 */
export function requestLspGoToDefinition(
  view: EditorView,
  hotkey = store.get(hotkeysAtom).getHotkey("cell.goToDefinition").key,
): boolean {
  for (const binding of view.state.facet(keymap).flat()) {
    if (
      binding.run !== marimoGoToDefinitionKeymap &&
      keymapBindingMatchesHotkey(binding, hotkey) &&
      binding.run?.(view)
    ) {
      return true;
    }
  }
  return false;
}

/**
 * Go to the definition under the cursor, falling back to the language server
 * when marimo cannot resolve the symbol (e.g. external library code).
 */
export function goToDefinitionWithLspFallback(view: EditorView): boolean {
  if (goToDefinitionAtCursorPosition(view)) {
    return true;
  }
  return requestLspGoToDefinition(view);
}

/**
 * Resolve where a variable is defined, without navigating. Prefers a local
 * (in-cell, scope-aware) definition at the usage position, then falls back to
 * the cell that declares it as a reactive notebook variable. Returns the target
 * editor and position, or null when nothing resolves.
 */
function resolveDefinition(
  view: EditorView,
  variableName: string,
  usagePosition?: number,
): { view: EditorView; from: number } | null {
  if (usagePosition !== undefined) {
    const from = findVariableDefinitionPosition(
      view.state,
      variableName,
      usagePosition,
    );
    if (from !== null) {
      return { view, from };
    }
  }

  // The variable may exist in another cell
  const editorWithVariable = getEditorForVariable(view, variableName);
  if (!editorWithVariable) {
    return null;
  }
  const from = findVariableDefinitionPosition(
    editorWithVariable.state,
    variableName,
  );
  if (from === null) {
    return null;
  }
  return { view: editorWithVariable, from };
}

/**
 * Go to the definition of the variable under the cursor.
 * @param view The editor view at which the command was invoked.
 */
export function goToDefinition(
  view: EditorView,
  variableName: string,
  usagePosition?: number,
): boolean {
  const location = resolveDefinition(view, variableName, usagePosition);
  if (!location) {
    return false;
  }
  goToPosition(location.view, location.from);
  return true;
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
