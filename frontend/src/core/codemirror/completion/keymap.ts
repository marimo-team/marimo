/* Copyright 2024 Marimo. All rights reserved. */
import { Prec, type Extension } from "@codemirror/state";
import {
  closeCompletion,
  completionStatus,
  completionKeymap as defaultCompletionKeymap,
} from "@codemirror/autocomplete";
import { keymap } from "@codemirror/view";
import type { EditorView } from "@codemirror/view";

export function completionKeymap(): Extension {
  const withoutEscape = defaultCompletionKeymap.filter(
    (binding) => binding.key !== "Escape",
  );

  const closeCompletionIfActive = (view: EditorView) => {
    const status = completionStatus(view.state);
    if (status === "pending") {
      closeCompletion(view);
      // Return false to propagate the Escape key
      return false;
    }
    // Use the default behavior: when the completion is Active
    // Return true to stop propagation of the Escape key
    return closeCompletion(view);
  };

  return Prec.highest(
    keymap.of([
      ...withoutEscape,
      // We add our own Escape binding to accept the completion
      // The default codemirror behavior is to close the completion
      // when Escape is pressed and the completion is Pending or Active.
      // We want to still close the completion, but allow propagation
      // of the Escape key when it is pending, so downstream hotkeys will work
      //
      // This happens when using Vim. If a completion is Pending and Esc is hit quickly,
      // we want to leave Insert mode AND close the completion.
      // When the completion is Active, we just want to close the completion.
      {
        key: "Escape",
        run: closeCompletionIfActive,
      },
    ]),
  );
}
