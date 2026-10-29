/* Copyright 2026 Marimo. All rights reserved. */

import { history, redo, undo } from "@codemirror/commands";
import { EditorSelection, EditorState, StateEffect } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { cellId } from "@/__tests__/branded";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { cellConfigExtension } from "../../config/extension";
import { prepareCellCodeUpdate } from "../cell-code";
import { languageMetadataField } from "../metadata";
import {
  adaptiveLanguageConfiguration,
  languageAdapterState,
  switchLanguage,
} from "../extension";
import {
  getEditorCodeAsPython,
  splitEditor,
  updateEditorCodeFromPython,
} from "../utils";

const views: EditorView[] = [];

afterEach(() => {
  for (const view of views.splice(0)) {
    view.destroy();
  }
});

function createEditor(doc: string) {
  const view = new EditorView({
    state: EditorState.create({
      doc,
      extensions: [
        history(),
        adaptiveLanguageConfiguration({
          completionConfig: {
            activate_on_typing: true,
            signature_hint_on_typing: false,
            copilot: false,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          cellId: cellId("cell1"),
          placeholderType: "marimo-import",
          lspConfig: {},
        }),
        cellConfigExtension({
          cellId: cellId("cell1"),
          completionConfig: {
            activate_on_typing: true,
            signature_hint_on_typing: false,
            copilot: false,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          placeholderType: "marimo-import",
          lspConfig: {
            pylsp: {
              enabled: true,
            },
          },
          diagnosticsConfig: {},
        }),
      ],
    }),
  });
  views.push(view);
  return view;
}

describe("getEditorCodeAsPython", () => {
  it("should return the entire editor text when no positions are specified", () => {
    const mockEditor = createEditor("print('Hello, World!')");
    const result = getEditorCodeAsPython(mockEditor);
    expect(result).toEqual("print('Hello, World!')");
  });

  it("should return a slice of the editor text when positions are specified", () => {
    const mockEditor = createEditor("print('Hello, World!')");
    const result = getEditorCodeAsPython(mockEditor, 0, 5);
    expect(result).toEqual("print");
  });

  it("should return a slice of the editor text when one position is specified", () => {
    const mockEditor = createEditor("print('Hello, World!')");
    const result = getEditorCodeAsPython(mockEditor, 5);
    expect(result).toEqual("('Hello, World!')");
  });
});

describe("updateEditorCodeFromPython", () => {
  it("applies text and metadata together, including metadata-only undo", () => {
    const view = createEditor('mo.md(r"hi")');
    switchLanguage(view, { language: "markdown" });
    const observed: Array<{ text: string; prefix: string }> = [];
    view.dispatch({
      effects: StateEffect.appendConfig.of(
        EditorView.updateListener.of((update) => {
          if (
            update.transactions.some(
              (tr) => tr.effects.length > 0 || tr.docChanged,
            )
          ) {
            observed.push({
              text: update.state.doc.toString(),
              prefix: update.state.field(languageMetadataField).quotePrefix,
            });
          }
        }),
      ),
    });
    observed.length = 0;

    updateEditorCodeFromPython(view, 'mo.md(f"hi")');
    expect(observed).toEqual([{ text: "hi", prefix: "f" }]);
    expect(undo(view)).toBe(true);
    expect(view.state.field(languageMetadataField).quotePrefix).toBe("r");
    expect(redo(view)).toBe(true);
    expect(view.state.field(languageMetadataField).quotePrefix).toBe("f");
  });

  it("clears incompatible history while applying a language fallback atomically", () => {
    const view = createEditor('mo.md("hi")');
    switchLanguage(view, { language: "markdown" });
    view.dispatch({ changes: { from: 2, insert: "!" } });
    const observed: Array<{ text: string; language: string }> = [];
    view.dispatch({
      effects: StateEffect.appendConfig.of(
        EditorView.updateListener.of((update) => {
          observed.push({
            text: update.state.doc.toString(),
            language: update.state.field(languageAdapterState).type,
          });
        }),
      ),
    });
    observed.length = 0;

    updateEditorCodeFromPython(view, "x = 1");
    expect(observed).toEqual([{ text: "x = 1", language: "python" }]);
    expect(undo(view)).toBe(false);
    view.dispatch({ changes: { from: 5, insert: "0" } });
    expect(undo(view)).toBe(true);
    expect(view.state.doc.toString()).toBe("x = 1");
  });

  it("maps the selection through separate edits and keeps the update undoable", () => {
    const view = createEditor("a = 1\nb = 2\nc = 3");
    view.dispatch({ selection: EditorSelection.range(6, 11) });
    updateEditorCodeFromPython(view, "alpha = 1\nb = 2\ncharlie = 3");
    expect(
      view.state.sliceDoc(
        view.state.selection.main.from,
        view.state.selection.main.to,
      ),
    ).toBe("b = 2");
    expect(undo(view)).toBe(true);
    expect(view.state.doc.toString()).toBe("a = 1\nb = 2\nc = 3");
  });

  it.each(["mo.md()", 'mo.md("hi")', 'df = mo.sql("SELECT 1")'])(
    "keeps Python mode when receiving %s",
    (code) => {
      const view = createEditor("mo.md");
      updateEditorCodeFromPython(view, code);
      expect({
        language: view.state.field(languageAdapterState).type,
        code: view.state.doc.toString(),
      }).toEqual({ language: "python", code });
    },
  );

  it.each([
    {
      language: "markdown",
      initial: 'mo.md("hi")',
      next: 'mo.md("bye")',
      text: "bye",
    },
    {
      language: "sql",
      initial: 'df = mo.sql("SELECT 1")',
      next: 'df = mo.sql("SELECT 2")',
      text: "SELECT 2",
    },
  ] as const)(
    "preserves compatible $language mode",
    ({ language, initial, next, text }) => {
      const view = createEditor(initial);
      switchLanguage(view, { language });
      updateEditorCodeFromPython(view, next);
      expect({
        language: view.state.field(languageAdapterState).type,
        code: view.state.doc.toString(),
      }).toEqual({ language, code: text });
    },
  );

  it.each([
    {
      language: "markdown",
      initial: 'mo.md("hi")',
      next: 'df = mo.sql("SELECT 1")',
    },
    {
      language: "sql",
      initial: 'df = mo.sql("SELECT 1")',
      next: 'mo.md("hi")',
    },
    { language: "markdown", initial: 'mo.md("hi")', next: "x = 1" },
  ] as const)(
    "falls back from $language to Python for $next",
    ({ language, initial, next }) => {
      const view = createEditor(initial);
      switchLanguage(view, { language });
      updateEditorCodeFromPython(view, next);
      expect({
        language: view.state.field(languageAdapterState).type,
        code: view.state.doc.toString(),
      }).toEqual({ language: "python", code: next });
    },
  );

  it("should update the editor code with the provided Python code", () => {
    const mockEditor = createEditor("");
    const pythonCode = "print('Hello, World!')";
    const result = updateEditorCodeFromPython(mockEditor, pythonCode);
    expect(result).toEqual(pythonCode);
    expect(mockEditor.state.doc.toString()).toEqual(pythonCode);
  });
});

describe("prepareCellCodeUpdate", () => {
  it("does not normalize an editor that already represents the source", () => {
    const view = createEditor('mo.md("hi")');
    switchLanguage(view, { language: "markdown" });
    expect(prepareCellCodeUpdate(view.state, 'mo.md("hi")')).toBeNull();
    view.dispatch({ changes: { from: 2, insert: "\n " } });
    const source = getEditorCodeAsPython(view);
    expect(prepareCellCodeUpdate(view.state, source)).toBeNull();
    expect(view.state.doc.toString()).toBe("hi\n ");
  });

  it.each(["", 'mo.md(f"hi {x}")'])(
    "prepares initialization from %j without mutating the editor",
    (initial) => {
      const view = createEditor(initial);
      const update = prepareCellCodeUpdate(view.state, 'mo.md(f"hi {x}")', {
        initialize: true,
      });
      expect(view.state.doc.toString()).toBe(initial);
      expect(view.state.field(languageAdapterState).type).toBe("python");
      expect(update).not.toBeNull();
      if (update) {
        view.dispatch(update);
      }
      expect(view.state.doc.toString()).toBe("hi {x}");
      expect(view.state.field(languageAdapterState).type).toBe("markdown");
      expect(view.state.field(languageMetadataField).quotePrefix).toBe("f");
      expect(undo(view)).toBe(false);
    },
  );
});

describe("splitEditor", () => {
  it("should handle the cursor being at the start of the line", () => {
    const mockEditor = createEditor("print('Hello')\nprint('Goodbye')");
    mockEditor.dispatch({
      selection: {
        anchor: "print('Hello')\n".length,
      },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual("print('Hello')");
    expect(result.afterCursorCode).toEqual("print('Goodbye')");
  });

  it("should handle the cursor being at the end of the line", () => {
    const mockEditor = createEditor("print('Hello')\nprint('Goodbye')");
    mockEditor.dispatch({
      selection: {
        anchor: "print('Hello')".length,
      },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual("print('Hello')");
    expect(result.afterCursorCode).toEqual("print('Goodbye')");
  });

  it("should split the editor code into two parts at the cursor position", () => {
    const mockEditor = createEditor("print('Hello')\nprint('Goodbye')");
    mockEditor.dispatch({
      selection: {
        anchor: 2,
      },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual("pr");
    expect(result.afterCursorCode).toEqual("int('Hello')\nprint('Goodbye')");
  });

  it("handle start and end of the docs", () => {
    let mockEditor = createEditor("print('Hello')\nprint('Goodbye')");
    mockEditor.dispatch({
      selection: { anchor: 0 },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual("");
    expect(result.afterCursorCode).toEqual("print('Hello')\nprint('Goodbye')");

    mockEditor = createEditor("print('Hello')\nprint('Goodbye')");
    mockEditor.dispatch({
      selection: { anchor: mockEditor.state.doc.length },
    });

    const result2 = splitEditor(mockEditor);
    expect(result2.beforeCursorCode).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );
    expect(result2.afterCursorCode).toEqual("");
  });

  it("handles markdown", () => {
    const mockEditor = createEditor("mo.md('Hello, World!')");
    // Set to markdown
    switchLanguage(mockEditor, { language: "markdown" });
    // Set cursor position
    mockEditor.dispatch({
      selection: { anchor: "Hello,".length },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual(`mo.md("""
Hello,
""")`);
    expect(result.afterCursorCode).toEqual(`mo.md("""
 World!
""")`);
  });

  // f-strings not currently supported
  it.fails("handles markdown with variables", () => {
    const mockEditor = createEditor('mo.md(f"""{a}\n{b}!""")');
    // Set to markdown
    switchLanguage(mockEditor, { language: "markdown" });
    // Set cursor position
    mockEditor.dispatch({
      selection: { anchor: "{a}\n".length },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual('mo.md(f"""{a}""")');
    expect(result.afterCursorCode).toEqual('mo.md(f"""{b}!""")');
  });
});
