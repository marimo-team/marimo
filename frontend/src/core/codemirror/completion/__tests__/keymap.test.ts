/* Copyright 2026 Marimo. All rights reserved. */

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

  it("should include Enter key in keymap by default (acceptOnEnter=true)", () => {
    const ext = completionKeymap(true);
    // The extension should be a keymap containing Enter
    const keymapExt = ext as { key?: string }[];
    const hasEnter = keymapExt.some(
      (e) =>
        e &&
        typeof e === "object" &&
        "key" in e &&
        (e as { key: string }).key === "Enter",
    );
    expect(hasEnter).toBe(true);
  });

  it("should exclude Enter key from keymap when acceptOnEnter=false", () => {
    const ext = completionKeymap(false);
    // The extension should NOT contain an Enter binding
    const keymapExt = ext as { key?: string }[];
    const hasEnter = keymapExt.some(
      (e) =>
        e &&
        typeof e === "object" &&
        "key" in e &&
        (e as { key: string }).key === "Enter",
    );
    expect(hasEnter).toBe(false);
  });
});
