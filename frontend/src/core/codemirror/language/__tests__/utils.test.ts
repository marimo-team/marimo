/* Copyright 2024 Marimo. All rights reserved. */
import {
  getEditorCodeAsPython,
  updateEditorCodeFromPython,
  splitEditor,
} from "../utils";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, it, expect } from "vitest";
import { adaptiveLanguageConfiguration, switchLanguage } from "../extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { CellId } from "@/core/cells/ids";
import { cellConfigExtension } from "../../config/extension";

function createEditor(doc: string) {
  return new EditorView({
    state: EditorState.create({
      doc,
      extensions: [
        adaptiveLanguageConfiguration({
          completionConfig: {
            activate_on_typing: true,
            copilot: false,
            codeium_api_key: null,
          },
          hotkeys: new OverridingHotkeyProvider({}),
          cellId: "cell1" as CellId,
          placeholderType: "marimo-import",
          lspConfig: {},
        }),
        cellConfigExtension(
          {
            activate_on_typing: true,
            copilot: false,
            codeium_api_key: null,
          },
          new OverridingHotkeyProvider({}),
          "marimo-import",
          {
            pylsp: {
              enabled: true,
            },
          },
        ),
      ],
    }),
  });
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
  it("should update the editor code with the provided Python code", () => {
    const mockEditor = createEditor("");
    const pythonCode = "print('Hello, World!')";
    const result = updateEditorCodeFromPython(mockEditor, pythonCode);
    expect(result).toEqual(pythonCode);
    expect(mockEditor.state.doc.toString()).toEqual(pythonCode);
  });
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
    switchLanguage(mockEditor, "markdown");
    // Set cursor position
    mockEditor.dispatch({
      selection: { anchor: "Hello,".length },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual('mo.md("""Hello,""")');
    expect(result.afterCursorCode).toEqual('mo.md(""" World!""")');
  });

  // f-strings not currently supported
  it.skip("handles markdown with variables", () => {
    const mockEditor = createEditor('mo.md(f"""{a}\n{b}!""")');
    // Set to markdown
    switchLanguage(mockEditor, "markdown");
    // Set cursor position
    mockEditor.dispatch({
      selection: { anchor: "{a}\n".length },
    });
    const result = splitEditor(mockEditor);
    expect(result.beforeCursorCode).toEqual('mo.md(f"""{a}""")');
    expect(result.afterCursorCode).toEqual('mo.md(f"""{b}!""")');
  });
});
