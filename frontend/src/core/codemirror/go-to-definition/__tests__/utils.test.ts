/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, test } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import {
  goToDefinitionAtCursorPosition,
  goToDefinitionAtPosition,
  hasDefinitionAtPosition,
} from "../utils";

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
  test("jumps to a reactive variable definition in another cell", async () => {
    const definingCell = cellId("defining-cell");
    const usageCell = cellId("usage-cell");
    const definingCode = "a = 10";
    const usageCode = "print(a)";

    const definingView = createEditor(definingCode, definingCode.length);
    const usageView = createEditor(usageCode, usageCode.indexOf("a"));
    views.push(definingView, usageView);

    const notebook = initialNotebookState();
    notebook.cellHandles[definingCell] = {
      current: { editorView: definingView, editorViewOrNull: definingView },
    };
    notebook.cellHandles[usageCell] = {
      current: { editorView: usageView, editorViewOrNull: usageView },
    };

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      [variableName("a")]: {
        dataType: "int",
        declaredBy: [definingCell],
        name: variableName("a"),
        usedBy: [usageCell],
        value: "10",
      },
    });

    const result = goToDefinitionAtCursorPosition(usageView);

    expect(result).toBe(true);
    await tick();
    expect(definingView.state.selection.main.head).toBe(0);
    expect(usageView.state.selection.main.head).toBe(usageCode.indexOf("a"));
  });

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
    const usageView = createEditor(
      usageCode,
      usageCode.lastIndexOf("mymodule"),
    );
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

describe("goToDefinitionAtPosition", () => {
  test("resolves the word at the given position, not the caret", async () => {
    const definingCell = cellId("defining-cell");
    const usageCell = cellId("usage-cell");
    const definingCode = "a = 10";
    const usageCode = "print(a)";

    const definingView = createEditor(definingCode, definingCode.length);
    // Caret is at the start of the cell, deliberately away from `a`.
    const usageView = createEditor(usageCode, 0);
    views.push(definingView, usageView);

    const notebook = initialNotebookState();
    notebook.cellHandles[definingCell] = {
      current: { editorView: definingView, editorViewOrNull: definingView },
    };
    notebook.cellHandles[usageCell] = {
      current: { editorView: usageView, editorViewOrNull: usageView },
    };

    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      [variableName("a")]: {
        dataType: "int",
        declaredBy: [definingCell],
        name: variableName("a"),
        usedBy: [usageCell],
        value: "10",
      },
    });

    const result = goToDefinitionAtPosition(usageView, usageCode.indexOf("a"));

    expect(result).toBe(true);
    await tick();
    expect(definingView.state.selection.main.head).toBe(0);
  });

  test("is a no-op when the position is not on a word", () => {
    const code = "a + b";
    const view = createEditor(code, 0);
    views.push(view);

    // The `+` operator is flanked by whitespace, so no identifier resolves.
    const result = goToDefinitionAtPosition(view, code.indexOf("+"));

    expect(result).toBe(false);
  });
});

describe("hasDefinitionAtPosition", () => {
  function registerVariable(name: string) {
    const definingCell = cellId("defining-cell");
    const definingView = createEditor(`${name} = 10`, 0);
    views.push(definingView);

    const notebook = initialNotebookState();
    notebook.cellHandles[definingCell] = {
      current: { editorView: definingView, editorViewOrNull: definingView },
    };
    store.set(notebookAtom, notebook);
    store.set(variablesAtom, {
      [variableName(name)]: {
        dataType: "int",
        declaredBy: [definingCell],
        name: variableName(name),
        usedBy: [],
        value: "10",
      },
    });
  }

  test("is true for a notebook variable used in another cell", () => {
    registerVariable("df");
    const code = "print(df)";
    const view = createEditor(code, 0);
    views.push(view);

    expect(hasDefinitionAtPosition(view, code.indexOf("df"))).toBe(true);
  });

  test("is false inside a string literal", () => {
    registerVariable("df");
    // `df` is a variable, but "hello" is just string contents.
    const code = 'x = "hello"';
    const view = createEditor(code, 0);
    views.push(view);

    expect(hasDefinitionAtPosition(view, code.indexOf("hello"))).toBe(false);
  });

  test("is true for a cell-local variable not in the notebook graph", () => {
    // `local_var` is defined only inside the function scope, so it never
    // appears in variablesAtom; it must still resolve locally.
    const code = `\
def f():
    local_var = 1
    return local_var`;
    const view = createEditor(code, 0);
    views.push(view);

    expect(hasDefinitionAtPosition(view, code.lastIndexOf("local_var"))).toBe(
      true,
    );
  });

  test("is false for a word that is not a variable", () => {
    const code = "print(value)";
    const view = createEditor(code, 0);
    views.push(view);

    // No variables registered and nothing declared locally, so neither
    // `print` nor `value` resolves.
    expect(hasDefinitionAtPosition(view, code.indexOf("print"))).toBe(false);
    expect(hasDefinitionAtPosition(view, code.indexOf("value"))).toBe(false);
  });
});
