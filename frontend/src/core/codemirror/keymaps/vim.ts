/* Copyright 2024 Marimo. All rights reserved. */

import { keymap } from "@codemirror/view";
import {
  isAtEndOfEditor,
  isAtStartOfEditor,
  isInVimNormalMode,
} from "../utils";

export function vimKeymapExtension(callbacks: {
  focusUp: () => void;
  focusDown: () => void;
}) {
  return [
    keymap.of([
      {
        key: "j",
        run: (ev) => {
          if (isAtEndOfEditor(ev, true) && isInVimNormalMode(ev)) {
            callbacks.focusDown();
            return true;
          }
          return false;
        },
      },
    ]),
    keymap.of([
      {
        key: "k",
        run: (ev) => {
          if (isAtStartOfEditor(ev) && isInVimNormalMode(ev)) {
            callbacks.focusUp();
            return true;
          }
          return false;
        },
      },
    ]),
  ];
}
