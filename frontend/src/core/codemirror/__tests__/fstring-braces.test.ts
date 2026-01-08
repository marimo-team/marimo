/* Copyright 2026 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { fStringBraceInputHandler } from "../cm";

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

describe("f-string brace auto-closing", () => {
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
    const result = fStringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"hello {}');
    expect(view.state.selection.main.head).toBe(9);
  });

  it("should auto-close braces in t-strings", () => {
    view = createEditor('t"hello ', 8);
    const result = fStringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('t"hello {}');
    expect(view.state.selection.main.head).toBe(9);
  });

  it("should auto-close braces in rf-strings", () => {
    view = createEditor('rf"hello ', 9);
    const result = fStringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('rf"hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in fr-strings", () => {
    view = createEditor('fr"hello ', 9);
    const result = fStringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('fr"hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in rt-strings", () => {
    view = createEditor('rt"hello ', 9);
    const result = fStringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('rt"hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in tr-strings", () => {
    view = createEditor('tr"hello ', 9);
    const result = fStringBraceInputHandler(view, 9, 9, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('tr"hello {}');
    expect(view.state.selection.main.head).toBe(10);
  });

  it("should auto-close braces in uppercase F-strings", () => {
    view = createEditor('F"hello ', 8);
    const result = fStringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('F"hello {}');
    expect(view.state.selection.main.head).toBe(9);
  });

  it("should NOT auto-close braces in regular strings", () => {
    view = createEditor('"hello ', 7);
    const result = fStringBraceInputHandler(view, 7, 7, "{");

    expect(result).toBe(false);
    expect(view.state.doc.toString()).toBe('"hello ');
  });

  it("should NOT auto-close braces in raw strings without f/t", () => {
    view = createEditor('r"hello ', 8);
    const result = fStringBraceInputHandler(view, 8, 8, "{");

    expect(result).toBe(false);
    expect(view.state.doc.toString()).toBe('r"hello ');
  });

  it("should NOT auto-close braces outside strings", () => {
    view = createEditor("x = ", 4);
    const result = fStringBraceInputHandler(view, 4, 4, "{");

    expect(result).toBe(false);
    expect(view.state.doc.toString()).toBe("x = ");
  });

  it("should NOT auto-close braces when typing other characters", () => {
    view = createEditor('f"hello ', 8);
    const result = fStringBraceInputHandler(view, 8, 8, "a");

    expect(result).toBe(false);
    expect(view.state.doc.toString()).toBe('f"hello ');
  });

  it("should handle braces at the start of f-string", () => {
    view = createEditor('f"', 2);
    const result = fStringBraceInputHandler(view, 2, 2, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"{}');
    expect(view.state.selection.main.head).toBe(3);
  });

  it("should handle braces in the middle of f-string content", () => {
    view = createEditor('f"hello world ', 14);
    const result = fStringBraceInputHandler(view, 14, 14, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"hello world {}');
    expect(view.state.selection.main.head).toBe(15);
  });

  it("should handle multiple braces in f-string", () => {
    view = createEditor('f"hello {} world ', 18);
    const result = fStringBraceInputHandler(view, 18, 18, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"hello {} world {}');
    expect(view.state.selection.main.head).toBe(19);
  });

  it("should handle empty f-string", () => {
    view = createEditor('f""', 2);
    const result = fStringBraceInputHandler(view, 2, 2, "{");

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe('f"{}"');
    expect(view.state.selection.main.head).toBe(3);
  });
});
