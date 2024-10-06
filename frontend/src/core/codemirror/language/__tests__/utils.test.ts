/* Copyright 2024 Marimo. All rights reserved. */
import {
  getEditorCodeAsPython,
  updateEditorCodeFromPython,
  splitEditor,
  extractHighlightedCode,
} from "../utils";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, it, expect, beforeAll } from "vitest";
import { adaptiveLanguageConfiguration, switchLanguage } from "../extension";
import { OverridingHotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { MovementCallbacks } from "../../cells/extensions";
import { store } from "@/core/state/jotai";
import { capabilitiesAtom } from "@/core/config/capabilities";

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
          showPlaceholder: true,
          enableAI: true,
          cellMovementCallbacks: {} as MovementCallbacks,
        }),
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

describe("extractHighlightedCode", () => {
  const pyLineOne = "import marimo as mo";
  const pyLineTwo = "import pandas as pd";
  const pyLineThree = "import numpy as np";
  const pythonCode = `${pyLineOne}\n${pyLineTwo}\n${pyLineThree}`;

  const sqlLineOne = "SELECT * FROM table";
  const sqlLineTwo = "WHERE column = value";
  const sqlLineThree = "ORDER BY column";
  const sqlCode = `df = mo.sql("""${sqlLineOne}\n${sqlLineTwo}\n${sqlLineThree}""")`;

  const mdLineOne = "Hello, World!";
  const mdLineTwo = "Goodbye, World!";
  const mdLineThree = "Hello, Goodbye!";
  const markdownCode = `mo.md('${mdLineOne}\n${mdLineTwo}\n${mdLineThree}')`;

  function getExtraction(editor: EditorView) {
    const result = extractHighlightedCode(editor);
    if (!result) {
      throw new Error("Result is null");
    }
    return result;
  }

  beforeAll(() => {
    store.set(capabilitiesAtom, {
      sql: true,
      terminal: true,
    });
  });

  it("extracts highlighted Python code at start", () => {
    const mockEditor = createEditor(pythonCode);
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(1).from,
        head: mockEditor.state.doc.line(2).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(`${pyLineOne}\n${pyLineTwo}`);
    expect(leftover).toEqual(`\n${pyLineThree}`);
  });

  it("extracts highlighted Python code in middle", () => {
    const mockEditor = createEditor(pythonCode);
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(2).from,
        head: mockEditor.state.doc.line(2).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(pyLineTwo);
    expect(leftover).toEqual(`${pyLineOne}\n${pyLineThree}`);
  });

  it("extracts highlighted Python code at end", () => {
    const mockEditor = createEditor(pythonCode);
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(3).from,
        head: mockEditor.state.doc.line(3).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(pyLineThree);
    expect(leftover).toEqual(`${pyLineOne}\n${pyLineTwo}`);
  });

  it("extracts no highlighted Python code if none", () => {
    const mockEditor = createEditor(pythonCode);
    mockEditor.dispatch({ selection: { anchor: 0, head: 0 } });
    const result = extractHighlightedCode(mockEditor);
    expect(result).toEqual(null);
  });

  it("extracts highlighted SQL code at start", () => {
    const mockEditor = createEditor(sqlCode);
    switchLanguage(mockEditor, "sql");
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(1).from,
        head: mockEditor.state.doc.line(2).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(leftover).toEqual(`df = mo.sql(
    """

    ${sqlLineThree}
    """\n)`);
    expect(highlighted).toEqual(`df = mo.sql(
    """
    ${sqlLineOne}
    ${sqlLineTwo}
    """\n)`);
  });

  it("extracts highlighted SQL code in middle", () => {
    const mockEditor = createEditor(sqlCode);
    switchLanguage(mockEditor, "sql");
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(2).from,
        head: mockEditor.state.doc.line(2).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(`df = mo.sql(
    """
    ${sqlLineTwo}
    """\n)`);
    expect(leftover).toEqual(`df = mo.sql(
    """
    ${sqlLineOne}
    ${sqlLineThree}
    """\n)`);
  });

  it("extracts highlighted SQL code at end", () => {
    const mockEditor = createEditor(sqlCode);
    switchLanguage(mockEditor, "sql");
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(3).from,
        head: mockEditor.state.doc.line(3).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(`df = mo.sql(
    """
    ${sqlLineThree}
    """\n)`);
    expect(leftover).toEqual(`df = mo.sql(
    """
    ${sqlLineOne}
    ${sqlLineTwo}
    """\n)`);
  });

  it("extracts no highlighted SQL code if none", () => {
    const mockEditor = createEditor(sqlCode);
    switchLanguage(mockEditor, "sql");
    mockEditor.dispatch({ selection: { anchor: 0, head: 0 } });
    const result = extractHighlightedCode(mockEditor);
    expect(result).toEqual(null);
  });

  it("extracts highlighted Markdown code at start", () => {
    const mockEditor = createEditor(markdownCode);
    switchLanguage(mockEditor, "markdown");
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(1).from,
        head: mockEditor.state.doc.line(2).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(leftover).toEqual(`mo.md(
    """

    ${mdLineThree}
    """\n)`);
    expect(highlighted).toEqual(`mo.md(
    """
    ${mdLineOne}
    ${mdLineTwo}
    """\n)`);
  });

  it("extracts highlighted Markdown code in middle", () => {
    const mockEditor = createEditor(markdownCode);
    switchLanguage(mockEditor, "markdown");
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(2).from,
        head: mockEditor.state.doc.line(2).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(`mo.md("""${mdLineTwo}""")`);
    expect(leftover).toEqual(`mo.md(
    """
    ${mdLineOne}
    ${mdLineThree}
    """\n)`);
  });

  it("extracts highlighted Markdown code at end", () => {
    const mockEditor = createEditor(markdownCode);
    switchLanguage(mockEditor, "markdown");
    mockEditor.dispatch({
      selection: {
        anchor: mockEditor.state.doc.line(3).from,
        head: mockEditor.state.doc.line(3).to,
      },
    });
    const [highlighted, leftover] = getExtraction(mockEditor);
    expect(highlighted).toEqual(`mo.md("""${mdLineThree}""")`);
    expect(leftover).toEqual(`mo.md(
    """
    ${mdLineOne}
    ${mdLineTwo}
    """\n)`);
  });

  it("extracts no highlighted Markdown code if none", () => {
    const mockEditor = createEditor(markdownCode);
    switchLanguage(mockEditor, "markdown");
    mockEditor.dispatch({ selection: { anchor: 0, head: 0 } });
    const result = extractHighlightedCode(mockEditor);
    expect(result).toEqual(null);
  });
});
