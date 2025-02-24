/* Copyright 2024 Marimo. All rights reserved. */
import type { KeymapConfig } from "@/core/config/config-schema";
import { logNever } from "@/utils/assertNever";
import { defaultKeymap, insertNewlineAndIndent } from "@codemirror/commands";
import { type Extension, Prec } from "@codemirror/state";
import { type EditorView, keymap } from "@codemirror/view";
import { getCM, vim } from "@replit/codemirror-vim";
import { vimKeymapExtension } from "./vim";
import { once } from "@/utils/once";

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
        // Filter out Enter from defaultKeymap
        keymap.of(defaultVimKeymap()),
        // Add Enter back for insert mode only
        keymap.of([
          {
            key: "Enter",
            run: (view) => {
              const cm = getCM(view);
              if (!cm?.state.vim?.insertMode) {
                return false;
              }
              return insertNewlineAndIndent(view);
            },
          },
        ]),
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

const defaultVimKeymap = once(() => {
  const toRemove = new Set(["Enter", "Ctrl-v"]);
  // Remove conflicting keys from the keymap
  // Enter (<CR>) adds a new line
  //   - it should just go to the next line
  // Ctrl-v goes to the bottom of the cell
  //   - should enter blockwise visual mode
  return defaultKeymap.filter(
    (k) => !toRemove.has(k.key || k.mac || k.linux || k.win || ""),
  );
});

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
