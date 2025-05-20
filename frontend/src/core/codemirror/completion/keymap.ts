/* Copyright 2024 Marimo. All rights reserved. */
import { Prec, type Extension } from "@codemirror/state";
import {
  closeCompletion,
  completionKeymap as defaultCompletionKeymap,
} from "@codemirror/autocomplete";
import { keymap } from "@codemirror/view";
import type { EditorView } from "@codemirror/view";
import { isInVimMode } from "../utils";

export function completionKeymap(): Extension {
  const withoutEscape = defaultCompletionKeymap.filter(
    (binding) => binding.key !== "Escape",
  );

  const closeCompletionAndPropagate = (view: EditorView) => {
    const status = closeCompletion(view);
    // When in vim mode, we need to propagate Escape to exit insert mode.
    if (isInVimMode(view)) {
      return false;
    }
    return status;
  };

  return Prec.highest(
    keymap.of([
      ...withoutEscape,
      // We add our own Escape binding to accept the completion
      // The default codemirror behavior is to close the completion
      // when Escape is pressed and the completion is Pending or Active.
      // We want to still close the completion, but allow propagation
      // of the Escape key, so downstream hotkeys (like leaving insert mode) will work.
      //
      // This happens when using Vim.
      {
        key: "Escape",
        run: closeCompletionAndPropagate,
      },
    ]),
  );
}
