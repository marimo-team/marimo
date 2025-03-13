/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  adaptiveLanguageConfiguration,
  getInitialLanguageAdapter,
  languageAdapterState,
  switchLanguage,
} from "../extension";
import { EditorState } from "@codemirror/state";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import { EditorView } from "@codemirror/view";
import type { CellId } from "@/core/cells/ids";
import { cellConfigExtension } from "../../config/extension";

function createState(content: string, selection?: { anchor: number }) {
  const state = EditorState.create({
    doc: content,
    extensions: [
      adaptiveLanguageConfiguration({
        cellId: "cell1" as CellId,
        completionConfig: {
          copilot: false,
          activate_on_typing: true,
          codeium_api_key: null,
        },
        lspConfig: {},
        hotkeys: new OverridingHotkeyProvider({}),
        placeholderType: "marimo-import",
      }),
      cellConfigExtension(
        {
          copilot: false,
          activate_on_typing: true,
          codeium_api_key: null,
        },
        new OverridingHotkeyProvider({}),
        "marimo-import",
        {},
      ),
    ],
    selection,
  });

  return state;
}

describe("getInitialLanguageAdapter", () => {
  it("should return python", () => {
    let state = createState("def f():\n  return 1");
    expect(getInitialLanguageAdapter(state).type).toBe("python");

    state = createState("");
    expect(getInitialLanguageAdapter(state).type).toBe("python");
  });

  it("should return markdown", () => {
    const state = createState("mo.md('hello')");
    expect(getInitialLanguageAdapter(state).type).toBe("markdown");
  });

  it("should return sql", () => {
    const state = createState("df = mo.sql('hello')");
    expect(getInitialLanguageAdapter(state).type).toBe("sql");
  });
});

describe("switchLanguage", () => {
  it("handles keepCodeAsIs is true", () => {
    const state = createState("print('Hello')\nprint('Goodbye')", {
      anchor: 2,
    });
    const mockEditor = new EditorView({ state });
    switchLanguage(mockEditor, "python", { keepCodeAsIs: true });
    expect(mockEditor.state.field(languageAdapterState).type).toBe("python");
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Check that the cursor position is maintained
    expect(mockEditor.state.selection.main.from).toEqual(2);

    // Check that the language adapter is updated
    expect(getInitialLanguageAdapter(mockEditor.state).type).toBe("python");

    // Switch to markdown
    switchLanguage(mockEditor, "markdown", { keepCodeAsIs: true });
    expect(mockEditor.state.field(languageAdapterState).type).toBe("markdown");
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Switch back to python
    switchLanguage(mockEditor, "python", { keepCodeAsIs: true });
    expect(mockEditor.state.field(languageAdapterState).type).toBe("python");
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Check that the cursor position is maintained
    expect(mockEditor.state.selection.main.from).toEqual(2);

    // Switch to sql
    switchLanguage(mockEditor, "sql", { keepCodeAsIs: true });
    expect(mockEditor.state.field(languageAdapterState).type).toBe("sql");
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Check that the cursor position is maintained
    expect(mockEditor.state.selection.main.from).toEqual(2);

    // Switch back to python
    switchLanguage(mockEditor, "python", { keepCodeAsIs: true });
    expect(mockEditor.state.field(languageAdapterState).type).toBe("python");
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Check that the cursor position is maintained
    expect(mockEditor.state.selection.main.from).toEqual(2);
  });

  it("handles keepCodeAsIs is false", () => {
    const state = createState("print('Hello')\nprint('Goodbye')", {
      anchor: 2,
    });
    const mockEditor = new EditorView({ state });
    switchLanguage(mockEditor, "python", { keepCodeAsIs: false });
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Check that the cursor position is maintained
    expect(mockEditor.state.selection.main.from).toEqual(2);

    // Switch to markdown
    switchLanguage(mockEditor, "markdown", { keepCodeAsIs: false });
    expect(mockEditor.state.doc.toString()).toEqual(
      "print('Hello')\nprint('Goodbye')",
    );

    // Switch back to python
    switchLanguage(mockEditor, "python", { keepCodeAsIs: false });
    expect(mockEditor.state.doc.toString()).toMatchInlineSnapshot(`
      "mo.md(
          r"""
          print('Hello')
          print('Goodbye')
          """
      )"
    `);

    // Switch to sql
    switchLanguage(mockEditor, "sql", { keepCodeAsIs: false });
    expect(mockEditor.state.doc.toString()).toMatchInlineSnapshot(`
      "print('Hello')
      print('Goodbye')"
    `);

    // Switch back to python
    switchLanguage(mockEditor, "python", { keepCodeAsIs: false });
    expect(mockEditor.state.doc.toString()).toMatchInlineSnapshot(`
      "_df = mo.sql(
          f"""
          print('Hello')
          print('Goodbye')
          """
      )"
    `);
  });
});
