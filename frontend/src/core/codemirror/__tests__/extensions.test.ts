/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as scrollUtils from "../../../utils/scroll";
import { scrollActiveLineIntoView } from "../extensions";
import { formattingChangeEffect } from "../format";

// Mock the smartScrollIntoView function
vi.mock("../../../utils/scroll", () => ({
  smartScrollIntoView: vi.fn(),
}));

describe("scrollActiveLineIntoView", () => {
  let view: EditorView;
  let mockAppElement: HTMLElement;

  beforeEach(() => {
    // Create a mock App element
    mockAppElement = document.createElement("div");
    mockAppElement.id = "App";
    document.body.append(mockAppElement);

    // Create an editor view with the scrollActiveLineIntoView extension
    view = new EditorView({
      state: EditorState.create({
        doc: "line 1\nline 2\nline 3",
        extensions: [scrollActiveLineIntoView()],
      }),
    });

    // Add the editor to the document
    document.body.append(view.dom);

    // Reset the mock
    vi.mocked(scrollUtils.smartScrollIntoView).mockClear();
  });

  afterEach(() => {
    // Clean up
    view.destroy();
    mockAppElement.remove();
    if (document.body.contains(view.dom)) {
      view.dom.remove();
    }
  });

  it("should not scroll when editor does not have focus", () => {
    // Simulate a height change and doc change
    view.dispatch({
      changes: { from: 0, to: 0, insert: "new line\n" },
    });

    // The editor doesn't have focus by default
    expect(vi.mocked(scrollUtils.smartScrollIntoView)).not.toHaveBeenCalled();
  });

  it("should scroll active line into view when height and doc change", () => {
    // Mock the focus state
    Object.defineProperty(view, "hasFocus", { value: true });

    // Add an active line element
    const activeLine = document.createElement("div");
    activeLine.className = "cm-activeLine cm-line";
    view.dom.append(activeLine);

    // Simulate a height change and doc change
    view.dispatch({
      changes: { from: 0, to: 0, insert: "new line\n" },
    });

    // Check that smartScrollIntoView was called with the right arguments
    expect(vi.mocked(scrollUtils.smartScrollIntoView)).toHaveBeenCalledWith(
      activeLine,
      {
        offset: { top: 30, bottom: 150 },
        body: mockAppElement,
      },
    );
  });

  it("should not scroll when there is no active line", () => {
    // Mock the focus state
    Object.defineProperty(view, "hasFocus", { value: true });

    // Simulate a height change and doc change
    view.dispatch({
      changes: { from: 0, to: 0, insert: "new line\n" },
    });

    // No active line element, so smartScrollIntoView should not be called
    expect(vi.mocked(scrollUtils.smartScrollIntoView)).not.toHaveBeenCalled();
  });

  it("should not scroll for formatting changes", () => {
    // Mock the focus state
    Object.defineProperty(view, "hasFocus", { value: true });

    // Add an active line element
    const activeLine = document.createElement("div");
    activeLine.className = "cm-activeLine cm-line";
    view.dom.append(activeLine);

    // Create a transaction with the formatting change effect
    const transaction = view.state.update({
      changes: { from: 0, to: 0, insert: "formatted line\n" },
      effects: [formattingChangeEffect.of(true)],
    });

    // Dispatch the transaction
    view.dispatch(transaction);

    // Should not scroll for formatting changes
    expect(vi.mocked(scrollUtils.smartScrollIntoView)).not.toHaveBeenCalled();
  });
});
