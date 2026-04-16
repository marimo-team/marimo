/* Copyright 2026 Marimo. All rights reserved. */

import { completionKeymap as defaultCompletionKeymap } from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { describe, expect, it } from "vitest";
import { completionKeymap, filterCompletionBindings } from "../keymap";

function hasEnterBinding(acceptOnEnter: boolean): boolean {
  const state = EditorState.create({
    extensions: [completionKeymap(acceptOnEnter)],
  });

  return state
    .facet(keymap)
    .flat()
    .some((binding) => binding.key === "Enter");
}

describe("completionKeymap", () => {
  it("upstream includes the macOS-only completion bindings we care about", () => {
    expect(
      defaultCompletionKeymap.some((binding) => binding.mac === "Alt-`"),
    ).toBe(true);
    expect(
      defaultCompletionKeymap.some((binding) => binding.mac === "Alt-i"),
    ).toBe(true);
  });

  it("removes Alt-backtick and Escape while keeping Alt-i", () => {
    const filtered = filterCompletionBindings(defaultCompletionKeymap);

    expect(filtered.some((binding) => binding.mac === "Alt-`")).toBe(false);
    expect(filtered.some((binding) => binding.key === "Escape")).toBe(false);
    expect(filtered.some((binding) => binding.mac === "Alt-i")).toBe(true);
  });

  it("includes Enter by default", () => {
    const filtered = filterCompletionBindings(defaultCompletionKeymap);
    expect(filtered.some((binding) => binding.key === "Enter")).toBe(true);
  });

  it("removes Enter when passed a keysToRemove set containing Enter", () => {
    const keysToRemove = new Set<string | undefined>([
      "Escape",
      "Alt-`",
      "Enter",
    ]);
    const filtered = filterCompletionBindings(
      defaultCompletionKeymap,
      keysToRemove,
    );
    expect(filtered.some((binding) => binding.key === "Enter")).toBe(false);
  });

  it("completionKeymap includes Enter when acceptOnEnter is true", () => {
    expect(hasEnterBinding(true)).toBe(true);
  });

  it("completionKeymap removes Enter when acceptOnEnter is false", () => {
    expect(hasEnterBinding(false)).toBe(false);
  });
});
