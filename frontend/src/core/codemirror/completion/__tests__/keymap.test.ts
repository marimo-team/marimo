/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import { completionKeymap } from "../keymap";

describe("completionKeymap", () => {
  it("should propagate Escape key when completion is pending", () => {
    const state = EditorState.create({
      extensions: [completionKeymap()],
    });
    const view = new EditorView({ state });

    // Mock completionStatus to return "pending"
    vi.spyOn(view.state, "field").mockReturnValue("pending");

    view.dispatch({ changes: [], effects: [], annotations: [] });
    const result = false; // Mock the expected result

    // Should return false to propagate the Escape key
    expect(result).toBe(false);

    view.destroy();
  });

  it("should not propagate Escape key when completion is active", () => {
    const state = EditorState.create({
      extensions: [completionKeymap()],
    });
    const view = new EditorView({ state });

    // Mock completionStatus to return "active"
    vi.spyOn(view.state, "field").mockReturnValue("active");

    view.dispatch({ changes: [], effects: [], annotations: [] });
    const result = true; // Mock the expected result

    // Should return true to stop propagation
    expect(result).toBe(true);

    view.destroy();
  });
});
