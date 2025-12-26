/* Copyright 2026 Marimo. All rights reserved. */

import {
  acceptCompletion,
  completionKeymap as defaultCompletionKeymap,
  moveCompletionSelection,
} from "@codemirror/autocomplete";
import { type Extension, Prec } from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { isInVimMode } from "../utils";

const KEYS_TO_REMOVE = new Set<string | undefined>([
  // Remove Escape since it affects exiting insert mode in Vim
  // Issue: https://github.com/marimo-team/marimo/issues/4351
  "Escape",

  // Remove Alt-` since this affects Italian keyboards from using backticks.
  // Issue: https://github.com/marimo-team/marimo/issues/5606
  // Alt-` is set to startCompletion on macOS which is likely not used,
  // Completions is still done via Ctrl-Space and Alt-i.
  // See https://github.com/codemirror/autocomplete/blob/ab0a89942b237bbc13735604b018d10c0101b5ea/src/index.ts#L40-L42
  "Alt-`",
]);

export function completionKeymap(): Extension {
  const withoutKeysToRemove = defaultCompletionKeymap.filter(
    (binding) => !KEYS_TO_REMOVE.has(binding.key),
  );

  return Prec.highest(
    keymap.of([
      ...withoutKeysToRemove,
      // We add our own Escape binding to accept the completion
      // The default codemirror behavior is to close the completion
      // when Escape is pressed and the completion is Pending or Active.
      // We want to still close the completion, but allow propagation
      // of the Escape key, so downstream hotkeys (like leaving insert mode) will work.
      //
      // This happens when using Vim.
      // Vim-specific completion keybindings
      {
        key: "Ctrl-y",
        run: (view) => {
          if (isInVimMode(view)) {
            return acceptCompletion(view);
          }
          return false;
        },
      },
      {
        key: "Ctrl-n",
        run: (view) => {
          if (isInVimMode(view)) {
            return moveCompletionSelection(true)(view);
          }
          return false;
        },
      },
      {
        key: "Ctrl-p",
        run: (view) => {
          if (isInVimMode(view)) {
            return moveCompletionSelection(false)(view);
          }
          return false;
        },
      },
    ]),
  );
}
