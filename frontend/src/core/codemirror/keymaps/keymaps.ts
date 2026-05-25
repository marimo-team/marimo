/* Copyright 2026 Marimo. All rights reserved. */

import {
  cursorCharLeft,
  cursorCharRight,
  cursorLineDown,
  cursorLineUp,
  insertNewlineAndIndent,
  defaultKeymap as originalDefaultKeymap,
  selectCharLeft,
  selectCharRight,
  selectLineDown,
  selectLineUp,
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
import { type CodeMirror, getCM, vim } from "@replit/codemirror-vim";
import type { KeymapConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { logNever } from "@/utils/assertNever";
import { once } from "@/utils/once";
import { cellActionsState } from "../cells/state";
import { vimKeymapExtension } from "./vim";

export const KEYMAP_PRESETS = ["default", "vim"] as const;

export function keymapBundle(
  config: KeymapConfig,
  hotkeys: HotkeyProvider,
): Extension[] {
  switch (config.preset) {
    case "default":
      return [keymap.of(defaultKeymap()), keymap.of(overrideKeymap(hotkeys))];
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
        // Arrow keys: use CodeMirror's cursor movement except in vim visual
        // mode, where vim must handle them to maintain selection.
        // The original cursorLineUp/Down bindings from the default keymap are
        // filtered out (see defaultVimKeymap) because their preventDefault
        // flag blocks vim's handler even when their run function returns false.
        keymap.of(vimVisualModeArrowKeyBindings()),
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
  copyLineDown,
  copyLineUp,
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
    {
      key: keymap.getHotkey("cell.copyLineUp").key,
      run: copyLineUp,
    },
    {
      key: keymap.getHotkey("cell.copyLineDown").key,
      run: copyLineDown,
    },
  ];
};

const defaultVimKeymap = once(() => {
  const toRemove = new Set([
    "Enter",
    "Ctrl-v",
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
  ]);
  // Remove conflicting keys from the keymap
  // Enter (<CR>) adds a new line
  //   - it should just go to the next line
  // Ctrl-v goes to the bottom of the cell
  //   - should enter blockwise visual mode
  // ArrowUp/ArrowDown (cursorLineUp/Down) always handle the event and have
  //   preventDefault, which blocks vim's handler from processing arrow keys.
  //   Replaced with visual-mode-aware wrappers in keymapBundle.
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

function isInVimVisualMode(cm: CodeMirror | undefined | null): boolean {
  return cm?.state.vim?.visualMode === true;
}

/**
 * In vim visual mode, arrow keys must be handled by vim to maintain selection.
 * Wrap each arrow key's run and shift so they defer to vim in visual mode,
 * but use CodeMirror's cursor commands in all other modes.
 */
function vimVisualModeArrowKeyBindings(): KeyBinding[] {
  const wrap =
    (cmd: Command): Command =>
    (view) => {
      if (isInVimVisualMode(getCM(view))) {
        return false;
      }
      return cmd(view);
    };

  return [
    {
      key: "ArrowDown",
      run: wrap(cursorLineDown),
      shift: wrap(selectLineDown),
    },
    {
      key: "ArrowUp",
      run: wrap(cursorLineUp),
      shift: wrap(selectLineUp),
    },
    {
      key: "ArrowLeft",
      run: wrap(cursorCharLeft),
      shift: wrap(selectCharLeft),
    },
    {
      key: "ArrowRight",
      run: wrap(cursorCharRight),
      shift: wrap(selectCharRight),
    },
  ];
}

export const visibleForTesting = {
  defaultKeymap,
  defaultVimKeymap,
  overrideKeymap,
  OVERRIDDEN_COMMANDS,
};
