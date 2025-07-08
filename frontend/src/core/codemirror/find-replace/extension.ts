/* Copyright 2024 Marimo. All rights reserved. */

import {
  highlightSelectionMatches,
  selectNextOccurrence,
} from "@codemirror/search";
import { keymap } from "@codemirror/view";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import {
  highlightTheme,
  searchHighlighter,
  searchState,
} from "./search-highlight";
import { closeFindReplacePanel, openFindReplacePanel } from "./state";

export function findReplaceBundle(hotkeys: HotkeyProvider) {
  return [
    keymap.of([
      {
        key: "Escape",
        // This is needed for Vim to go back to normal mode
        preventDefault: false,
        run: closeFindReplacePanel,
      },
      {
        key: hotkeys.getHotkey("cell.selectNextOccurrence").key,
        preventDefault: true,
        run: selectNextOccurrence,
      },
      {
        key: hotkeys.getHotkey("cell.findAndReplace").key,
        preventDefault: true,
        run: openFindReplacePanel,
      },
    ]),
    highlightSelectionMatches(),
    searchHighlighter,
    searchState,
    highlightTheme,
  ];
}
