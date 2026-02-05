/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import { replaceEditorContent } from "../replace-editor-content";

describe("replaceEditorContent", () => {
  it("should replace content when editor doesn't have focus", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "original content",
      }),
    });

    // Editor doesn't have focus by default
    expect(view.hasFocus).toBe(false);

    replaceEditorContent(view, "new content");

    expect(view.state.doc.toString()).toBe("new content");
    // Cursor position is not preserved when not focused
    expect(view.state.selection.main.head).toBe(0);

    view.destroy();
  });

  it("should preserve cursor position when editor has focus (same line)", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Hello World",
        selection: { anchor: 6 }, // Position after "Hello "
      }),
    });

    // Mock hasFocus to return true
    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    expect(view.hasFocus).toBe(true);

    // Replace with similar length content on same line
    replaceEditorContent(view, "Goodbye Everyone");

    expect(view.state.doc.toString()).toBe("Goodbye Everyone");

    // Cursor should stay at the same column (6) since it's still within the line
    const newCursorPos = view.state.selection.main.head;
    expect(newCursorPos).toBe(6);

    view.destroy();
  });

  it("should preserve cursor at beginning when focused", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Hello World",
        selection: { anchor: 0 }, // At beginning
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "Goodbye Everyone");

    expect(view.state.doc.toString()).toBe("Goodbye Everyone");
    // Cursor should stay at beginning
    expect(view.state.selection.main.head).toBe(0);

    view.destroy();
  });

  it("should clamp cursor when line shrinks", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Hello World",
        selection: { anchor: 11 }, // At end (column 11)
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    // Replace with shorter content
    replaceEditorContent(view, "Goodbye");

    expect(view.state.doc.toString()).toBe("Goodbye");
    // Cursor should be clamped to end of line since column 11 > line length (7)
    expect(view.state.selection.main.head).toBe(7);

    view.destroy();
  });

  it("should handle empty document", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "",
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "new content");

    expect(view.state.doc.toString()).toBe("new content");
    expect(view.state.selection.main.head).toBe(0);

    view.destroy();
  });

  it("should do nothing when content is the same", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "same content",
        selection: { anchor: 5 },
      }),
    });

    const dispatchSpy = vi.spyOn(view, "dispatch");

    replaceEditorContent(view, "same content");

    // No dispatch should have been called
    expect(dispatchSpy).not.toHaveBeenCalled();
    expect(view.state.doc.toString()).toBe("same content");
    expect(view.state.selection.main.head).toBe(5);

    view.destroy();
  });

  it("should handle cursor in middle of focused document", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "The quick brown fox jumps",
        selection: { anchor: 10 }, // After "The quick " (column 10)
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    // Replace with longer content
    replaceEditorContent(view, "The extremely quick brown fox jumps over");

    expect(view.state.doc.toString()).toBe(
      "The extremely quick brown fox jumps over",
    );

    // Cursor should stay at same column (10) on same line
    const newCursorPos = view.state.selection.main.head;
    expect(newCursorPos).toBe(10);

    view.destroy();
  });

  it("should respect preserveCursor=false when focused", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Hello World",
        selection: { anchor: 6 },
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "Goodbye Everyone", { preserveCursor: false });

    expect(view.state.doc.toString()).toBe("Goodbye Everyone");
    // When preserveCursor is false, cursor is not explicitly set
    // so it defaults to 0
    expect(view.state.selection.main.head).toBe(0);

    view.destroy();
  });

  it("should handle newlines and multiline content", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Line 1\nLine 2\nLine 3",
        // Cursor at position 10: "Line 1\nLi|ne 2\nLine 3"
        // Line 2, column 2 (after "Li")
        selection: { anchor: 10 },
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "Line 1\nLine 2 updated\nLine 3\nLine 4");

    expect(view.state.doc.toString()).toBe(
      "Line 1\nLine 2 updated\nLine 3\nLine 4",
    );

    // Cursor should stay on line 2 at column 2 (after "Li")
    // "Line 1\nLi|ne 2 updated\nLine 3\nLine 4"
    const newCursorPos = view.state.selection.main.head;
    expect(newCursorPos).toBe(10); // Same position, line 2 column 2

    view.destroy();
  });

  it("should move cursor up when line is deleted", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Line 1\nLine 2\nLine 3",
        selection: { anchor: 14 }, // Line 3, start of line
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    // Replace with only 2 lines (line 3 is deleted)
    replaceEditorContent(view, "Line 1\nLine 2");

    expect(view.state.doc.toString()).toBe("Line 1\nLine 2");

    // Cursor should move to end of last available line
    const newCursorPos = view.state.selection.main.head;
    expect(newCursorPos).toBe(13); // End of "Line 1\nLine 2"

    view.destroy();
  });

  it("should stay at end of line when new line is added", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Hello World",
        selection: { anchor: 11 }, // At end (column 11)
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "Hello World\nSome new line");

    expect(view.state.doc.toString()).toBe("Hello World\nSome new line");
    const newCursorPos = view.state.selection.main.head;
    expect(newCursorPos).toBe(11);

    view.destroy();
  });

  it("should preserve cursor on same line with column clamping", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "def function_with_long_name():",
        selection: { anchor: 25 }, // Near end of line
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    // Replace with shorter line
    replaceEditorContent(view, "def fn():");

    expect(view.state.doc.toString()).toBe("def fn():");

    // Cursor should be clamped to end of shorter line
    const newCursorPos = view.state.selection.main.head;
    expect(newCursorPos).toBe(9); // End of "def fn():"

    view.destroy();
  });

  it("should handle selection range (collapses to head position)", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Hello World",
        selection: { anchor: 0, head: 5 }, // "Hello" selected
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "Goodbye Everyone");

    expect(view.state.doc.toString()).toBe("Goodbye Everyone");
    // Selection head (5) is preserved as cursor position
    expect(view.state.selection.main.head).toBe(5);
    expect(view.state.selection.main.anchor).toBe(5);

    view.destroy();
  });

  it("should handle replacing with empty string", () => {
    const view = new EditorView({
      state: EditorState.create({
        doc: "Some content to clear",
        selection: { anchor: 10 },
      }),
    });

    Object.defineProperty(view, "hasFocus", {
      get: () => true,
      configurable: true,
    });

    replaceEditorContent(view, "");

    expect(view.state.doc.toString()).toBe("");
    // Cursor should be at position 0 (only valid position in empty doc)
    expect(view.state.selection.main.head).toBe(0);

    view.destroy();
  });
});
