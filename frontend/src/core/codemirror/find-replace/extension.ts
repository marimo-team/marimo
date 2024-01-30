/* Copyright 2024 Marimo. All rights reserved. */
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import {
  highlightSelectionMatches,
  selectNextOccurrence,
} from "@codemirror/search";
import { keymap } from "@codemirror/view";
import { closeFindReplacePanel, openFindReplacePanel } from "./state";
import {
  highlightTheme,
  searchHighlighter,
  searchState,
} from "./search-highlight";

export function findReplaceBundle() {
  return [
    keymap.of([
      {
        key: "Escape",
        // This is needed for Vim to go back to normal mode
        preventDefault: false,
        run: closeFindReplacePanel,
      },
      {
        key: HOTKEYS.getHotkey("cell.selectNextOccurrence").key,
        preventDefault: true,
        run: selectNextOccurrence,
      },
      {
        key: HOTKEYS.getHotkey("cell.findAndReplace").key,
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
