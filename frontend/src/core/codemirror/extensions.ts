/* Copyright 2023 Marimo. All rights reserved. */
import { EditorView, keymap, placeholder } from "@codemirror/view";
import { CellId } from "../model/ids";
import { formatEditorViews } from "./format";
import { smartScrollIntoView } from "../../utils/scroll";
import { HOTKEYS } from "@/core/hotkeys/hotkeys";

/**
 * A placeholder that will be shown when the editor is empty and support auto-complete on right arrow.
 */
export function smartPlaceholderExtension(text: string) {
  return [
    placeholder(text),
    keymap.of([
      {
        key: "ArrowRight",
        preventDefault: true,
        run: (cm) => {
          // if empty, insert the placeholder
          if (cm.state.doc.length === 0) {
            cm.dispatch({
              changes: {
                from: 0,
                to: cm.state.doc.length,
                insert: text,
              },
            });
            // move cursor to end of placeholder
            cm.dispatch({
              selection: {
                anchor: cm.state.doc.length,
                head: cm.state.doc.length,
              },
            });
            return true;
          }
          return false;
        },
      },
    ]),
  ];
}

/**
 * Add a keymap to format the code in the editor.
 */
export function formatKeymapExtension(
  cellId: CellId,
  updateCellCode: (
    cellId: CellId,
    code: string,
    formattingChange: boolean
  ) => void
) {
  return keymap.of([
    {
      key: HOTKEYS.getHotkey("cell.format").key,
      preventDefault: true,
      run: (ev) => {
        formatEditorViews({ [cellId]: ev }, updateCellCode);
        return true;
      },
    },
  ]);
}

export function scrollActiveLineIntoView() {
  return EditorView.updateListener.of((update) => {
    // A new line was added, scroll the active line into view
    if (update.heightChanged && update.docChanged) {
      const activeLines = update.view.dom.getElementsByClassName(
        "cm-activeLine cm-line"
      );
      // Only scroll if there is an active line
      if (activeLines.length === 1) {
        const activeLine = activeLines[0] as HTMLElement;
        smartScrollIntoView(activeLine, {
          top: 30,
          bottom: 90,
        });
      }
    }
  });
}
