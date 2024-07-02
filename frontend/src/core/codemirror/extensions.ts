/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView, keymap } from "@codemirror/view";
import type { CellId } from "../cells/ids";
import { formatEditorViews } from "./format";
import { toggleToLanguage } from "./commands";
import { smartScrollIntoView } from "../../utils/scroll";
import { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { invariant } from "@/utils/invariant";
import type { CodeCallbacks } from "./cells/extensions";

/**
 * Add a keymap to format the code in the editor.
 */
export function formatKeymapExtension(
  cellId: CellId,
  callbacks: CodeCallbacks,
  hotkeys: HotkeyProvider,
) {
  const { updateCellCode, afterToggleMarkdown } = callbacks;
  return keymap.of([
    {
      key: hotkeys.getHotkey("cell.format").key,
      preventDefault: true,
      run: (ev) => {
        formatEditorViews({ [cellId]: ev }, updateCellCode);
        return true;
      },
    },
    {
      key: hotkeys.getHotkey("cell.viewAsMarkdown").key,
      preventDefault: true,
      run: (ev) => {
        const response = toggleToLanguage(ev, "markdown");
        if (response === "markdown") {
          afterToggleMarkdown();
        }
        return response !== false;
      },
    },
  ]);
}

/**
 * Scroll the active line into view when the editor is resized,
 * with an offset.
 *
 * This is necessary when typings at the edges of the editor
 * and the user is blocked by the hovering action bar.
 */
export function scrollActiveLineIntoView() {
  return EditorView.updateListener.of((update) => {
    // A new line was added, scroll the active line into view
    if (update.heightChanged && update.docChanged) {
      const activeLines = update.view.dom.getElementsByClassName(
        "cm-activeLine cm-line",
      );
      // Only scroll if there is an active line
      if (activeLines.length === 1) {
        const activeLine = activeLines[0] as HTMLElement;
        const appEl = document.getElementById("App");
        invariant(appEl, "App not found");
        smartScrollIntoView(activeLine, { top: 30, bottom: 150 }, appEl);
      }
    }
  });
}
