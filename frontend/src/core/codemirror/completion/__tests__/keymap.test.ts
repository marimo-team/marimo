/* Copyright 2026 Marimo. All rights reserved. */

import {
  autocompletion,
  completeFromList,
  completionKeymap as defaultCompletionKeymap,
} from "@codemirror/autocomplete";
import { EditorState } from "@codemirror/state";
import { EditorView, runScopeHandlers } from "@codemirror/view";
import { afterEach, describe, expect, it } from "vitest";
import { completionKeymap } from "../keymap";

describe("completionKeymap", () => {
  let view: EditorView | null = null;

  afterEach(() => {
    view?.destroy();
    view = null;
  });

  function createView() {
    view = new EditorView({
      state: EditorState.create({
        extensions: [
          autocompletion({
            override: [completeFromList(["completion-option"])],
          }),
          completionKeymap(),
        ],
      }),
    });
    return view;
  }

  it("does not intercept Alt-backtick on macOS", () => {
    expect(
      defaultCompletionKeymap.some((binding) => binding.mac === "Alt-`"),
    ).toBe(true);

    const cm = createView();
    const event = new KeyboardEvent("keydown", {
      key: "`",
      code: "Backquote",
      altKey: true,
      bubbles: true,
      cancelable: true,
    });

    expect(runScopeHandlers(cm, event, "editor")).toBe(false);
  });

  it("only targets the problematic macOS backtick shortcut", () => {
    expect(
      defaultCompletionKeymap.some((binding) => binding.mac === "Alt-`"),
    ).toBe(true);
    expect(
      defaultCompletionKeymap.some((binding) => binding.mac === "Alt-i"),
    ).toBe(true);
  });
});
