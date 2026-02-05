/* Copyright 2026 Marimo. All rights reserved. */
import { syntaxTree } from "@codemirror/language";
import type { Extension } from "@codemirror/state";
import { EditorView } from "@codemirror/view";

export function stringBraceInputHandler(
  view: EditorView,
  from: number,
  to: number,
  text: string,
): boolean {
  if (text !== "{") {
    return false;
  }

  if (from !== to) {
    return false;
  }

  const tree = syntaxTree(view.state);
  const node = tree.resolveInner(from, -1);

  if (!node?.type.name.includes("String")) {
    return false;
  }

  view.dispatch({
    changes: { from, to, insert: "{}" },
    selection: { anchor: from + 1 },
    userEvent: "input.type",
  });
  return true;
}

export function stringsAutoCloseBraces(): Extension {
  return EditorView.inputHandler.of(stringBraceInputHandler);
}
