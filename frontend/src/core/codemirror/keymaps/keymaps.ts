/* Copyright 2024 Marimo. All rights reserved. */
import type { KeymapConfig } from "@/core/config/config-schema";
import { logNever } from "@/utils/assertNever";
import { defaultKeymap } from "@codemirror/commands";
import { type Extension, Prec } from "@codemirror/state";
import { type EditorView, keymap } from "@codemirror/view";
import { vim } from "@replit/codemirror-vim";
import { vimKeymapExtension } from "./vim";

export const KEYMAP_PRESETS = ["default", "vim"] as const;

export function keymapBundle(
  config: KeymapConfig,
  callbacks: {
    focusUp: () => void;
    focusDown: () => void;
    deleteCell: () => void;
  },
): Extension[] {
  switch (config.preset) {
    case "default":
      return [
        keymap.of(defaultKeymap),
        keymap.of([
          {
            key: "Escape",
            preventDefault: true,
            run: (cm) => {
              cm.contentDOM.blur();
              return true;
            },
          },
        ]),
      ];
    case "vim":
      return [
        keymap.of(defaultKeymap),
        // delete the cell on double press of "d", if the cell is empty
        Prec.high(
          doubleCharacterListener(
            "d",
            (view) => view.state.doc.toString() === "",
            (view) => {
              if (view.state.doc.toString() === "") {
                callbacks.deleteCell();
                return true;
              }
              return false;
            },
          ),
        ),
        // Base vim mode
        vim({ status: false }),
        // Custom vim keymaps for cell navigation
        Prec.high(vimKeymapExtension(callbacks)),
      ];
    default:
      logNever(config.preset);
      return [];
  }
}

/**
 * Listen for a double keypress of a character and call a callback.
 */
function doubleCharacterListener(
  character: string,
  predicate: (view: EditorView) => boolean,
  onDoubleCharacter: (view: EditorView) => boolean,
): Extension {
  let lastKey = "";
  let lastKeyTime = 0;
  return keymap.of([
    {
      any: (view, event) => {
        const key = event.key;
        const time = event.timeStamp;

        // Different key or false predicate
        if (key !== character || !predicate(view)) {
          lastKey = "";
          lastKeyTime = 0;
          return false;
        }

        // Second keypress
        if (lastKey === character && time - lastKeyTime < 500) {
          const result = onDoubleCharacter(view);
          // Was handled
          if (result) {
            lastKey = "";
            lastKeyTime = 0;
            return true;
          }
        }

        // Track keypress
        lastKey = key;
        lastKeyTime = time;
        return false;
      },
    },
  ]);
}
