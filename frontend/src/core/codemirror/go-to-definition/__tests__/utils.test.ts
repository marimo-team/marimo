/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState, type Extension } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { afterEach, describe, expect, test, vi } from "vitest";
import { cellId, variableName } from "@/__tests__/branded";
import { initialNotebookState, notebookAtom } from "@/core/cells/cells";
import { store } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import {
  canRequestDefinitionAtPosition,
  goToDefinitionAtCursorPosition,
  goToDefinitionAtPosition,
  goToDefinitionAtPositionWithLspFallback,
  goToDefinitionWithLspFallback,
  lspGoToDefinitionSupport,
  marimoGoToDefinitionKeymap,
  requestLspGoToDefinition,
} from "../utils";

async function tick(): Promise<void> {
  await new Promise((resolve) => requestAnimationFrame(resolve));
}

function createEditor(
  content: string,
  selection: number,
  extensions: Extension[] = [],
) {
  const state = EditorState.create({
    doc: content,
    selection: { anchor: selection },
    extensions: [python(), ...extensions],
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
describe("goToDefinitionWithLspFallback", () => {
  test("falls through to LSP when marimo cannot resolve the symbol", () => {
    const lspGoToDefinition = vi.fn(() => true);
    const view = new EditorView({
      state: EditorState.create({
        doc: "parser.add_argument('--foo')",
        selection: { anchor: "parser.add_argument".indexOf("add_argument") },
        extensions: [
          python(),
          keymap.of([{ key: "F12", run: lspGoToDefinition }]),
        ],
      }),
      parent: document.body,
    });
    views.push(view);

    const result = goToDefinitionWithLspFallback(view);

    expect(result).toBe(true);
    expect(lspGoToDefinition).toHaveBeenCalledOnce();
  });

  test("does not invoke LSP when marimo resolves the symbol", async () => {
    const lspGoToDefinition = vi.fn(() => true);
    const code = "a = 10\nprint(a)";
    const view = new EditorView({
      state: EditorState.create({
        doc: code,
        selection: { anchor: code.indexOf("a", 3) },
        extensions: [
          python(),
          keymap.of([{ key: "F12", run: lspGoToDefinition }]),
        ],
      }),
      parent: document.body,
    });
    views.push(view);

    const result = goToDefinitionWithLspFallback(view);

    expect(result).toBe(true);
    expect(lspGoToDefinition).not.toHaveBeenCalled();
    await tick();
    expect(view.state.selection.main.head).toBe(0);
  });

  test("falls through with a modified shortcut like Ctrl-F12", () => {
    const lspGoToDefinition = vi.fn(() => true);
    const view = new EditorView({
      state: EditorState.create({
        doc: "parser.add_argument('--foo')",
        selection: { anchor: "parser.add_argument".indexOf("add_argument") },
        extensions: [
          python(),
          keymap.of([{ key: "Ctrl-F12", run: lspGoToDefinition }]),
        ],
      }),
      parent: document.body,
    });
    views.push(view);

    const result = requestLspGoToDefinition(view, "Ctrl-F12");

    expect(result).toBe(true);
    expect(lspGoToDefinition).toHaveBeenCalledOnce();
  });

  test("skips marimo's local keymap when requesting LSP", () => {
    const lspGoToDefinition = vi.fn(() => true);
    const code = "a = 1\nprint(a)";
    const view = createEditor(code, code.lastIndexOf("a"), [
      keymap.of([
        { key: "F12", run: marimoGoToDefinitionKeymap },
        { key: "F12", run: lspGoToDefinition },
      ]),
    ]);
    views.push(view);

    expect(requestLspGoToDefinition(view)).toBe(true);
    expect(lspGoToDefinition).toHaveBeenCalledOnce();
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

  test("is a no-op on an operator adjacent to variables", () => {
    const code = "a+b";
    const view = createEditor(code, 0);
    views.push(view);

    expect(goToDefinitionAtPosition(view, code.indexOf("+"))).toBe(false);
  });

  test("moves the caret to the clicked variable before using LSP", () => {
    const lspGoToDefinition = vi.fn(() => true);
    const code = "parser.add_argument('--foo')";
    const position = code.indexOf("add_argument");
    const view = createEditor(code, 0, [
      lspGoToDefinitionSupport.of(true),
      keymap.of([{ key: "F12", run: lspGoToDefinition }]),
    ]);
    views.push(view);

    const result = goToDefinitionAtPositionWithLspFallback(view, position);

    expect(result).toBe(true);
    expect(view.state.selection.main.head).toBe(position);
    expect(lspGoToDefinition).toHaveBeenCalledOnce();
  });
});

describe("canRequestDefinitionAtPosition", () => {
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

    expect(canRequestDefinitionAtPosition(view, code.indexOf("df"))).toBe(true);
  });

  test("is false inside a string literal", () => {
    registerVariable("df");
    // `df` is a variable, but "hello" is just string contents.
    const code = 'x = "hello"';
    const view = createEditor(code, 0);
    views.push(view);

    expect(canRequestDefinitionAtPosition(view, code.indexOf("hello"))).toBe(
      false,
    );
  });

  test("is false when string contents match a notebook variable", () => {
    registerVariable("df");
    const code = 'print("df")';
    const view = createEditor(code, 0);
    views.push(view);

    expect(canRequestDefinitionAtPosition(view, code.indexOf("df"))).toBe(
      false,
    );
  });

  test("is false when comment text matches a notebook variable", () => {
    registerVariable("df");
    const code = "# inspect df";
    const view = createEditor(code, 0);
    views.push(view);

    expect(canRequestDefinitionAtPosition(view, code.indexOf("df"))).toBe(
      false,
    );
  });

  test("does not resolve a property as a notebook variable", () => {
    registerVariable("value");
    const code = "object.value";
    const view = createEditor(code, 0);
    views.push(view);

    expect(canRequestDefinitionAtPosition(view, code.indexOf("value"))).toBe(
      false,
    );
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

    expect(
      canRequestDefinitionAtPosition(view, code.lastIndexOf("local_var")),
    ).toBe(true);
  });

  test("is false for a word that is not a variable", () => {
    const code = "print(value)";
    const view = createEditor(code, 0);
    views.push(view);

    // No variables registered and nothing declared locally, so neither
    // `print` nor `value` resolves.
    expect(canRequestDefinitionAtPosition(view, code.indexOf("print"))).toBe(
      false,
    );
    expect(canRequestDefinitionAtPosition(view, code.indexOf("value"))).toBe(
      false,
    );
  });

  test("is true for an unresolved variable when LSP is available", () => {
    const code = "parser.add_argument('--foo')";
    const view = createEditor(code, 0, [lspGoToDefinitionSupport.of(true)]);
    views.push(view);

    expect(
      canRequestDefinitionAtPosition(view, code.indexOf("add_argument")),
    ).toBe(true);
  });
});
