/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { syntaxTree } from "@codemirror/language";

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
  const state = view.state;
  const tree = syntaxTree(state);

  let found = false;
  let from = 0;

  tree.iterate({
    enter: (node) => {
      if (found) {
        return false;
      } // Stop traversal if found

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
    return true;
  }
  return false;
}
