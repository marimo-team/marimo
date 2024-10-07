/* Copyright 2024 Marimo. All rights reserved. */
import { acceptCompletion, startCompletion } from "@codemirror/autocomplete";
import { indentMore, indentWithTab } from "@codemirror/commands";
import { indentUnit } from "@codemirror/language";
import type { Extension } from "@codemirror/state";
import { keymap, type EditorView } from "@codemirror/view";

/**
 * Setup keybindings for tab handling.
 */
export function tabHandling(): Extension[] {
  return [
    indentUnit.of("    "),
    keymap.of([
      // Tabs for completion
      {
        key: "Tab",
        run: (cm) => {
          return (
            acceptCompletion(cm) ||
            startCompletionIfAtEndOfLine(cm) ||
            insertTab(cm)
          );
        },
        preventDefault: true,
      },
      // Tab-more/tab-less
      indentWithTab,
    ]),
  ];
}

/**
 * Custom insert tab that inserts our custom tab character (4 spaces).
 * Adapted from https://github.com/codemirror/commands/blob/d0c97ba5de9d1b5d42fa5a713f0c9d64a3134a3c/src/commands.ts#L854-L858
 */
function insertTab(cm: EditorView) {
  const { state } = cm;
  if (state.selection.ranges.some((r) => !r.empty)) {
    return indentMore(cm);
  }
  const indent = state.facet(indentUnit);
  cm.dispatch(
    state.update(state.replaceSelection(indent), {
      scrollIntoView: true,
      userEvent: "input",
    }),
  );
  return true;
}

/**
 * Start completion if the cursor is at the end of a line.
 */
function startCompletionIfAtEndOfLine(cm: EditorView): boolean {
  const { from, to } = cm.state.selection.main;
  if (from !== to) {
    // this is a selection
    return false;
  }

  const line = cm.state.doc.lineAt(to);
  const textBeforeCursor = line.text.slice(0, to - line.from);

  if (textBeforeCursor.trim() === "") {
    // Cursor is at the beginning of a line or in whitespace
    return false;
  }

  if (to === line.to) {
    // Cursor is at the end of a line
    return startCompletion(cm);
  }

  return false;
}

export const visibleForTesting = {
  insertTab,
  startCompletionIfAtEndOfLine,
};
