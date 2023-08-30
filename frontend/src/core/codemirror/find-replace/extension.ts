/* Copyright 2023 Marimo. All rights reserved. */
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import {
  highlightSelectionMatches,
  selectNextOccurrence,
} from "@codemirror/search";
import { keymap } from "@codemirror/view";
import { closeFindReplacePanel, openFindReplacePanel } from "./state";

export function findReplaceBundle() {
  return [
    keymap.of([
      {
        key: "Escape",
        preventDefault: true,
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
  ];
}
