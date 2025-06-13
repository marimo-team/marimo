/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, test } from "vitest";
import { goToVariableDefinition } from "../commands";

function createEditor(content: string) {
  const state = EditorState.create({
    doc: content,
    extensions: [python()],
  });

  const view = new EditorView({
    state,
    parent: document.body,
  });

  return view;
}

let view: EditorView | null = null;

afterEach(() => {
  if (view) {
    view.destroy();
    view = null;
  }
});

describe("goToVariableDefinition", () => {
  test("selects the variable when it exists", async () => {
    view = createEditor("#comment\nmyVar = 10\nprint(myVar)");
    const result = goToVariableDefinition(view, "myVar");

    expect(result).toBe(true);
    await new Promise((resolve) => requestAnimationFrame(resolve));
    expect(view.state.selection.main.from).toBe(9);
    expect(view.state.selection.main.to).toBe(9);
  });

  test("does not select the variable when it does not exist", () => {
    view = createEditor("#comment\nmyVar = 10;\nprint(myVar)");
    const result = goToVariableDefinition(view, "nonExistentVar");

    expect(result).toBe(false);
    expect(view.state.selection.main.from).toBe(0);
    expect(view.state.selection.main.to).toBe(0);
  });

  test("does not select the variable when it exists in a comment or string", () => {
    view = createEditor("#comment\n# myVar\nprint('myVar')");
    const result = goToVariableDefinition(view, "myVar");

    expect(result).toBe(false);
    expect(view.state.selection.main.from).toBe(0);
    expect(view.state.selection.main.to).toBe(0);
  });
});
