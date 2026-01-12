/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { stringBraceInputHandler } from "../string-braces";

function createEditor(
  initialContent: string,
  cursorPosition: number,
): EditorView {
  const state = EditorState.create({
    doc: initialContent,
    selection: { anchor: cursorPosition },
    extensions: [python()],
  });

  const view = new EditorView({
    state,
    parent: document.body,
  });

  return view;
}

describe("string brace auto-closing", () => {
  let view: EditorView;

  afterEach(() => {
    if (view) {
      view.destroy();
      if (document.body.contains(view.dom)) {
        view.dom.remove();
      }
    }
  });

  it("should auto-close braces in f-strings", () => {
    view = createEditor('f"hello ', 8);
    const result = stringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"hello {}');
    expect(view.state.selection.main.head).toBe(9);
  });

  it("should auto-close braces in regular double-quoted strings", () => {
    view = createEditor('"hello ', 7);
    const result = stringBraceInputHandler(view, 7, 7, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('"hello {}');
    expect(view.state.selection.main.head).toBe(8);
  });

  it("should auto-close braces in rf-strings", () => {
    view = createEditor('rf"hello ', 9);
    const result = stringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('rf"hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in fr-strings", () => {
    view = createEditor('fr"hello ', 9);
    const result = stringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('fr"hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in single-quoted strings", () => {
    view = createEditor("'hello ", 7);
    const result = stringBraceInputHandler(view, 7, 7, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe("'hello {}");
    expect(view.state.selection.main.head).toBe(8);
  });

  it("should auto-close braces in uppercase F-strings", () => {
    view = createEditor('F"hello ', 8);
    const result = stringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('F"hello {}');
    expect(view.state.selection.main.head).toBe(9);
  });

  it("should auto-close braces in raw strings without f/t", () => {
    view = createEditor('r"hello ', 8);
    const result = stringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('r"hello {}');
    expect(view.state.selection.main.head).toBe(9);
  });

  // Handled by other CodeMirror handler(s)
  it("should NOT auto-close braces outside strings", () => {
    view = createEditor("x = ", 4);
    const result = stringBraceInputHandler(view, 4, 4, "{");

    expect(result).toBe(false);
    expect(view.state.doc.toString()).toBe("x = ");
  });

  it("should NOT auto-close braces when typing other characters", () => {
    view = createEditor('f"hello ', 8);
    const result = stringBraceInputHandler(view, 8, 8, "a");

    expect(result).toBe(false);
    expect(view.state.doc.toString()).toBe('f"hello ');
  });

  it("should handle braces at the start of string", () => {
    view = createEditor('f"', 2);
    const result = stringBraceInputHandler(view, 2, 2, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"{}');
    expect(view.state.selection.main.head).toBe(3);
  });

  it("should handle braces in the middle of string content", () => {
    view = createEditor('f"hello world ', 14);
    const result = stringBraceInputHandler(view, 14, 14, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"hello world {}');
    expect(view.state.selection.main.head).toBe(15);
  });

  it("should handle multiple braces in string", () => {
    view = createEditor('f"hello {} world', 16);
    const result = stringBraceInputHandler(view, 16, 16, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"hello {} world{}');
    expect(view.state.selection.main.head).toBe(17);
  });

  it("should handle empty string", () => {
    view = createEditor('f""', 2);
    const result = stringBraceInputHandler(view, 2, 2, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"{}"');
    expect(view.state.selection.main.head).toBe(3);
  });

  it("should auto-close braces in triple-quoted strings", () => {
    view = createEditor('"""hello ', 9);
    const result = stringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('"""hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in triple-quoted f-strings", () => {
    view = createEditor('f"""hello ', 10);
    const result = stringBraceInputHandler(view, 10, 10, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"""hello {}');
    expect(view.state.selection.main.head).toBe(11);
  });

  it("should auto-close braces in triple single-quoted strings", () => {
    view = createEditor("'''hello ", 9);
    const result = stringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe("'''hello {}");
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in triple single-quoted f-strings", () => {
    view = createEditor("f'''hello ", 10);
    const result = stringBraceInputHandler(view, 10, 10, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe("f'''hello {}");
    expect(view.state.selection.main.head).toBe(11);
  });

  it("should NOT auto-close braces when text is selected", () => {
    view = createEditor('f"hello world"', 8);
    // User has selected "world" (from position 8 to 13)
    const result = stringBraceInputHandler(view, 8, 13, "{");

    expect(result).toBe(false);
    // Document should remain unchanged since we return false
    expect(view.state.doc.toString()).toBe('f"hello world"');
  });
});
