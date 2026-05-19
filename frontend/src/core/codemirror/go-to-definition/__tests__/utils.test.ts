/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, test } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import { goToDefinitionAtCursorPosition } from "../utils";

async function tick(): Promise<void> {
  await new Promise((resolve) => requestAnimationFrame(resolve));
}

function createEditor(content: string, selection: number) {
  const state = EditorState.create({
    doc: content,
    selection: { anchor: selection },
    extensions: [python()],
  });

  return new EditorView({
    state,
    parent: document.body,
  });
}

const views: EditorView[] = [];

afterEach(() => {
  for (const view of views.splice(0)) {
    view.destroy();
  }

  store.set(notebookAtom, initialNotebookState());
  store.set(variablesAtom, {});
});

describe("goToDefinitionAtCursorPosition", () => {
  test("prefers the current-cell local definition over a reactive global", async () => {
    const globalCell = cellId("global-cell");
    const localCell = cellId("local-cell");
    const globalCode = `\
a = 10
print(a)`;
    const localCode = `\
def test():
    a = 20
    print(a)`;

    const globalView = createEditor(globalCode, globalCode.length);
    const localView = createEditor(localCode, localCode.lastIndexOf("a"));
    views.push(globalView, localView);

    const notebook = initialNotebookState();
    notebook.cellHandles[globalCell] = {
      current: { editorView: globalView, editorViewOrNull: globalView },
    };
    notebook.cellHandles[localCell] = {
      current: { editorView: localView, editorViewOrNull: localView },
    };

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      [variableName("a")]: {
        dataType: "int",
        declaredBy: [globalCell],
        name: variableName("a"),
        usedBy: [localCell],
        value: "10",
      },
    });

    const result = goToDefinitionAtCursorPosition(localView);

    expect(result).toBe(true);
    await tick();
    expect(localView.state.selection.main.head).toBe(
      localCode.indexOf("a = 20"),
    );
    expect(globalView.state.selection.main.head).toBe(globalCode.length);
  });

  test("keeps private variables within the current cell", async () => {
    const code = `\
_x = 10
output = _x + 10`;
    const view = createEditor(code, code.lastIndexOf("_x"));
    views.push(view);

    const result = goToDefinitionAtCursorPosition(view);

    expect(result).toBe(true);
    await tick();
    expect(view.state.selection.main.head).toBe(code.indexOf("_x = 10"));
  });

  test("falls through to cross-cell when in-cell occurrence is only a module path in a from-import", async () => {
    // Regression: ImportStatement used to register every VariableName child
    // (the module path and pre-`as` names) as in-cell declarations, so the
    // local-first short-circuit would steal F12 from cross-cell resolution.
    const moduleCell = cellId("module-cell");
    const usageCell = cellId("usage-cell");
    const moduleCode = `mymodule = 100`;
    const usageCode = `\
from mymodule import something
print(mymodule)`;

    const moduleView = createEditor(moduleCode, moduleCode.length);
    const usageView = createEditor(usageCode, usageCode.lastIndexOf("mymodule"));
    views.push(moduleView, usageView);

    const notebook = initialNotebookState();
    notebook.cellHandles[moduleCell] = {
      current: { editorView: moduleView, editorViewOrNull: moduleView },
    } as never;
    notebook.cellHandles[usageCell] = {
      current: { editorView: usageView, editorViewOrNull: usageView },
    } as never;

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      [variableName("mymodule")]: {
        dataType: "int",
        declaredBy: [moduleCell],
        name: variableName("mymodule"),
        usedBy: [usageCell],
        value: "100",
      },
    });

    const result = goToDefinitionAtCursorPosition(usageView);

    expect(result).toBe(true);
    await tick();
    // Cross-cell jump: moduleView's cursor should land on `mymodule = 100`.
    expect(moduleView.state.selection.main.head).toBe(
      moduleCode.indexOf("mymodule"),
    );
  });
});
