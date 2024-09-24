/* Copyright 2024 Marimo. All rights reserved. */
// @vitest-environment jsdom
import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import { tabHandling, visibleForTesting } from "../tabs";
import { EditorView } from "@codemirror/view";
import { autocompletion, startCompletion } from "@codemirror/autocomplete";

const { insertTab, startCompletionIfAtEndOfLine } = visibleForTesting;

vi.mock("@codemirror/autocomplete", async (imported) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const mod: any = await imported();
  return {
    ...mod,
    startCompletion: vi.fn().mockImplementation(mod.startCompletion),
  };
});

describe("insertTab", () => {
  it("should insert 4 spaces when cursor is not in a selection", () => {
    const doc = "Hello\nWorld";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
    });

    const result = insertTab(view);

    expect(result).toBe(true);
    expect(view.state.doc.toString()).toBe("    Hello\nWorld");
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should call indentMore when there is a selection", () => {
    const doc = "Hello\nWorld";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 0, head: 5 },
    });

    insertTab(view);

    expect(view.state.doc.toString()).toBe("    Hello\nWorld");
    expect(startCompletion).not.toHaveBeenCalled();
  });
});

describe("startCompletionIfAtEndOfLine", () => {
  beforeAll(() => {
    // Mock getBoundingClientRect
    document.createRange = vi.fn(() => ({
      getBoundingClientRect: vi.fn(() => ({ width: 0 })),
      setStart: vi.fn(),
      setEnd: vi.fn(),
      getClientRects: vi.fn(() => [{ width: 0 }]),
    }));
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should start completion at the end of a non-empty line", () => {
    const doc = "Hello";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],

      selection: { anchor: 5, head: 5 },
    });

    const result = startCompletionIfAtEndOfLine(view);
    expect(result).toBe(true);

    expect(startCompletion).toHaveBeenCalled();
  });

  it("should not start completion if cursor is not at the end of a line", () => {
    const doc = "Hello World";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 5, head: 5 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should not start completion if line is empty", () => {
    const doc = "\n";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 0, head: 0 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should not start completion if cursor is in a selection", () => {
    const doc = "Hello";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 0, head: 5 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should not start completion if cursor is at the end of an empty line", () => {
    const doc = "\n";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 1, head: 1 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should not start completion if cursor is at the end of a line with only whitespace", () => {
    const doc = "    ";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 4, head: 4 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should not start completion if cursor is at the beginning of a line", () => {
    const doc = "Hello\nWorld";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 6, head: 6 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });

  it("should not start completion if cursor is in whitespace", () => {
    const doc = "Hello\n    World";
    const view = new EditorView({
      doc,
      extensions: [autocompletion({}), tabHandling()],
      selection: { anchor: 6, head: 6 },
    });

    const result = startCompletionIfAtEndOfLine(view);

    expect(result).toBe(false);
    expect(startCompletion).not.toHaveBeenCalled();
  });
});
