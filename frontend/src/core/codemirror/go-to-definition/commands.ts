/* Copyright 2024 Marimo. All rights reserved. */

import { syntaxTree } from "@codemirror/language";
import { EditorView } from "@codemirror/view";

function goToPosition(view: EditorView, from: number): void {
  view.focus();
  // Wait for the next frame, otherwise codemirror will
  // add a cursor from a pointer click.
  requestAnimationFrame(() => {
    view.dispatch({
      selection: {
        anchor: from,
        head: from,
      },
      // Unfortunately, EditorView.scrollIntoView does
      // not support smooth scrolling.
      effects: EditorView.scrollIntoView(from, {
        y: "center",
      }),
    });
  });
}

/**
 * This function will select the first occurrence of the given variable name,
 * for a given editor view.
 * @param view The editor view which contains the variable name.
 * @param variableName The name of the variable to select, if found in the editor.
 */
export function goToVariableDefinition(
  view: EditorView,
  variableName: string,
): boolean {
  const { state } = view;
  const tree = syntaxTree(state);

  let found = false;
  let from = 0;

  tree.iterate({
    enter: (node) => {
      if (found) {
        return false;
      } // Stop traversal if found

      // Skip function/lambda bodies entirely
      if (
        node.name === "LambdaExpression" ||
        node.name === "FunctionDefinition"
      ) {
        return false;
      }

      // Check if the node is an identifier and matches the variable name
      if (
        node.name === "VariableName" &&
        state.doc.sliceString(node.from, node.to) === variableName
      ) {
        from = node.from;
        found = true;
        return false; // Stop traversal
      }

      // Skip comments and strings
      if (node.name === "Comment" || node.name === "String") {
        return false;
      }
    },
  });

  if (found) {
    goToPosition(view, from);
    return true;
  }
  return false;
}

/**
 * This function jumps to a given position in the editor.
 * @param view The editor view which contains the variable name.
 * @param lineNumber The line number to jump to.
 */
export function goToLine(view: EditorView, lineNumber: number): boolean {
  const line = view.state.doc.line(lineNumber);
  goToPosition(view, line.from);
  return true;
}
