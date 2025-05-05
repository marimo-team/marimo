/* Copyright 2024 Marimo. All rights reserved. */
import type { KeymapConfig } from "@/core/config/config-schema";
import { logNever } from "@/utils/assertNever";
import {
  defaultKeymap as originalDefaultKeymap,
  insertNewlineAndIndent,
  toggleBlockComment,
  toggleComment,
} from "@codemirror/commands";
import { type Extension, Prec } from "@codemirror/state";
import {
  type Command,
  type EditorView,
  type KeyBinding,
  keymap,
} from "@codemirror/view";
import { getCM, vim } from "@replit/codemirror-vim";
import { vimKeymapExtension } from "./vim";
import { once } from "@/utils/once";
import { cellActionsState } from "../cells/state";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";

export const KEYMAP_PRESETS = ["default", "vim"] as const;

export function keymapBundle(
  config: KeymapConfig,
  hotkeys: HotkeyProvider,
): Extension[] {
  switch (config.preset) {
    case "default":
      return [
        keymap.of(defaultKeymap()),
        keymap.of(overrideKeymap(hotkeys)),
        // Should be the last thing to close when Escape is pressed
        Prec.low(
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
        ),
      ];
    case "vim":
      return [
        keymap.of(defaultVimKeymap()),
        keymap.of(overrideKeymap(hotkeys)),
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
                const actions = view.state.facet(cellActionsState);
                actions.deleteCell();
                return true;
              }
              return false;
            },
          ),
        ),
        // Base vim mode
        vim({ status: false }),
        // Custom vim keymaps for cell navigation
        Prec.high(vimKeymapExtension()),
      ];
    default:
      logNever(config.preset);
      return [];
  }
}

// Override commands from the default keymap
// https://github.com/codemirror/commands/blob/6.8.1/src/commands.ts#L1043
// We can add more from the default keymap if needed over time,
// but there are currently 50+ commands in the default keymap
const OVERRIDDEN_COMMANDS = new Set<Command | undefined>([
  toggleComment,
  toggleBlockComment,
]);

const defaultKeymap = once(() => {
  // Filter out commands that are in the overridden set
  return originalDefaultKeymap.filter((k) => !OVERRIDDEN_COMMANDS.has(k.run));
});

const overrideKeymap = (keymap: HotkeyProvider): readonly KeyBinding[] => {
  return [
    {
      key: keymap.getHotkey("cell.toggleComment").key,
      run: toggleComment,
    },
    {
      key: keymap.getHotkey("cell.toggleBlockComment").key,
      run: toggleBlockComment,
    },
  ];
};

const defaultVimKeymap = once(() => {
  const toRemove = new Set(["Enter", "Ctrl-v"]);
  // Remove conflicting keys from the keymap
  // Enter (<CR>) adds a new line
  //   - it should just go to the next line
  // Ctrl-v goes to the bottom of the cell
  //   - should enter blockwise visual mode
  return defaultKeymap().filter(
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

export const visibleForTesting = {
  defaultKeymap,
  defaultVimKeymap,
  overrideKeymap,
  OVERRIDDEN_COMMANDS,
};
