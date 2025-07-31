/* Copyright 2024 Marimo. All rights reserved. */

import { python } from "@codemirror/lang-python";
import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { insertDebuggerAtLine } from "../debugging";

describe("insertDebuggerAtLine", () => {
  let container: HTMLElement;
  let view: EditorView;

  beforeEach(() => {
    // Create a container for the editor
    container = document.createElement("div");
    document.body.append(container);
  });

  afterEach(() => {
    // Clean up after each test
    view.destroy();
    container.remove();
  });

  it("should insert a debugger statement at the beginning of a line", () => {
    // Create an editor with some python code
    const initialDoc = 'def test():\n  print("hello")\n  return True';

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Insert a debugger statement at line 2
    const result = insertDebuggerAtLine(view, 2);

    // Check the result
    expect(result).toBe(true);

    // Check the updated document content
    const expectedDoc =
      'def test():\n  breakpoint()\n  print("hello")\n  return True';
    expect(view.state.doc.toString()).toBe(expectedDoc);

    // Check that the cursor is at the end of the breakpoint line
    const cursorPos = view.state.selection.main.head;
    const breakpointLine = view.state.doc.line(2);
    expect(cursorPos).toBe(breakpointLine.to);
  });

  it("should match the indentation of the target line", () => {
    // Create an editor with code that has different indentation levels
    const initialDoc =
      'def test():\n    if True:\n        print("nested")\n    return True';

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Insert a debugger statement at the deeply indented line
    const result = insertDebuggerAtLine(view, 3);

    // Check the result
    expect(result).toBe(true);

    // Check that the debugger statement has the same indentation
    const expectedDoc =
      'def test():\n    if True:\n        breakpoint()\n        print("nested")\n    return True';
    expect(view.state.doc.toString()).toBe(expectedDoc);

    // Check that the cursor is at the end of the breakpoint line
    const cursorPos = view.state.selection.main.head;
    const breakpointLine = view.state.doc.line(3);
    expect(cursorPos).toBe(breakpointLine.to);
  });

  it("should handle the first line correctly", () => {
    const initialDoc = "x = 1\ny = 2";

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Insert a debugger statement at line 1
    const result = insertDebuggerAtLine(view, 1);

    // Check the result
    expect(result).toBe(true);

    // Check the updated document content
    const expectedDoc = "breakpoint()\nx = 1\ny = 2";
    expect(view.state.doc.toString()).toBe(expectedDoc);
  });

  it("should return false for invalid line numbers", () => {
    const initialDoc = "x = 1\ny = 2";

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Try to insert a debugger statement at an invalid line
    const result = insertDebuggerAtLine(view, 999);

    // Check the result
    expect(result).toBe(false);

    // Check that the document was not modified
    expect(view.state.doc.toString()).toBe(initialDoc);
  });

  it("should handle empty lines correctly", () => {
    const initialDoc = "x = 1\n\ny = 2";

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Insert a debugger statement at the empty line
    const result = insertDebuggerAtLine(view, 2);

    // Check the result
    expect(result).toBe(true);

    // Check the updated document content
    const expectedDoc = "x = 1\nbreakpoint()\n\ny = 2";
    expect(view.state.doc.toString()).toBe(expectedDoc);
  });

  it("should handle tab indentation correctly", () => {
    const initialDoc =
      'def test():\n\tif True:\n\t\tprint("tabbed")\n\treturn True';

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Insert a debugger statement at the tabbed line
    const result = insertDebuggerAtLine(view, 3);

    // Check the result
    expect(result).toBe(true);

    // Check that the debugger statement has the same tab indentation
    const expectedDoc =
      'def test():\n\tif True:\n\t\tbreakpoint()\n\t\tprint("tabbed")\n\treturn True';
    expect(view.state.doc.toString()).toBe(expectedDoc);
  });

  it("should skip insertion if line already contains breakpoint()", () => {
    const initialDoc = "x = 1\nbreakpoint()\ny = 2";

    view = new EditorView({
      state: EditorState.create({
        doc: initialDoc,
        extensions: [python()],
      }),
      parent: container,
    });

    // Try to insert a debugger statement at line 2 which already has breakpoint()
    const result = insertDebuggerAtLine(view, 2);

    // Check the result
    expect(result).toBe(true);

    // Check that the document was not modified
    expect(view.state.doc.toString()).toBe(initialDoc);
  });
});
