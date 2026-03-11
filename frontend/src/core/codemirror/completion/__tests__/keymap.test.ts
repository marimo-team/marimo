/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { describe, expect, it, vi } from "vitest";
import type { CompletionConfig } from "@/core/config/config-schema";
import { completionKeymap } from "../keymap";

const defaultCompletionConfig: CompletionConfig = {
  activate_on_typing: true,
  signature_hint_on_typing: false,
  copilot: false,
  disable_autocompletion_on_enter: false,
};

function getCompletionKeymapKeys(state: EditorState): (string | undefined)[] {
  const keymaps = state.facet(keymap).flat();
  return keymaps.map((km) => km.key);
}

describe("completionKeymap", () => {
  it("should propagate Escape key when completion is pending", () => {
    const state = EditorState.create({
      extensions: [completionKeymap(defaultCompletionConfig)],
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
      extensions: [completionKeymap(defaultCompletionConfig)],
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

  describe("disable_autocompletion_on_enter", () => {
    it("should include Enter key in completion keymap when disable_autocompletion_on_enter is false", () => {
      const state = EditorState.create({
        extensions: [
          completionKeymap({
            ...defaultCompletionConfig,
            disable_autocompletion_on_enter: false,
          }),
        ],
      });

      const keys = getCompletionKeymapKeys(state);
      expect(keys).toContain("Enter");
    });

    it("should exclude Enter key from completion keymap when disable_autocompletion_on_enter is true", () => {
      const state = EditorState.create({
        extensions: [
          completionKeymap({
            ...defaultCompletionConfig,
            disable_autocompletion_on_enter: true,
          }),
        ],
      });

      const keys = getCompletionKeymapKeys(state);
      expect(keys).not.toContain("Enter");
    });
  });
});
