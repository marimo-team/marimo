/* Copyright 2024 Marimo. All rights reserved. */
import { KeymapConfig } from "@/core/config/config-schema";
import { logNever } from "@/utils/assertNever";
import { defaultKeymap } from "@codemirror/commands";
import { Extension, Prec } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { vim, Vim } from "@replit/codemirror-vim";
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
      // Delete a cell with :dcell
      Vim.defineEx("dcell", "dcell", () => {
        callbacks.deleteCell();
      });
      return [
        vimKeymapExtension(callbacks),
        // delete the cell on double press of "d", if the cell is empty
        Prec.highest(
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
        vim({ status: false }),
        keymap.of(defaultKeymap),
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
