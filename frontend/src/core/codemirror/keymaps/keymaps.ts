/* Copyright 2023 Marimo. All rights reserved. */
import { KeymapConfig } from "@/core/config/config-schema";
import { logNever } from "@/utils/assertNever";
import { defaultKeymap } from "@codemirror/commands";
import { Extension, Prec } from "@codemirror/state";
import { EditorView, ViewPlugin, keymap } from "@codemirror/view";
import { CodeMirror, getCM, vim, Vim } from "@replit/codemirror-vim";

export const KEYMAP_PRESETS = ["default", "vim"] as const;

export function keymapBundle(
  config: KeymapConfig,
  callbacks: {
    deleteCell: () => void;
  }
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
        ViewPlugin.define((view) => {
          const listener = doubleCharacterListener(
            "d",
            (view) => view.state.doc.toString() === "",
            (view) => {
              if (view.state.doc.toString() === "") {
                callbacks.deleteCell();
                return true;
              }
              return false;
            }
          );
          getCM(view)?.on("vim-keypress", (key: string) => {
            listener(key, view);
          });
          return {};
        }),
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
  onDoubleCharacter: (view: EditorView) => boolean
): (key: string, view: EditorView) => boolean {
  let lastKey = "";
  let lastKeyTime = 0;
  return (key: string, view: EditorView) => {
    const time = Date.now();

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
  };
}
