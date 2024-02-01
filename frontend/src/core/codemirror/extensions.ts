/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView, keymap, placeholder } from "@codemirror/view";
import { CellId } from "../cells/ids";
import { formatEditorViews } from "./format";
import { smartScrollIntoView } from "../../utils/scroll";
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import { CellActions } from "../cells/cells";
import { invariant } from "@/utils/invariant";

function acceptPlaceholder(cm: EditorView, text: string) {
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
}

/**
 * A placeholder that will be shown when the editor is empty and support
 * auto-complete on right arrow or Tab.
 */
export function smartPlaceholderExtension(text: string) {
  return [
    placeholder(text),
    keymap.of([
      {
        key: "ArrowRight",
        preventDefault: true,
        run: (cm) => acceptPlaceholder(cm, text),
      },
      {
        key: "Tab",
        preventDefault: true,
        run: (cm) => acceptPlaceholder(cm, text),
      },
    ]),
  ];
}

/**
 * Add a keymap to format the code in the editor.
 */
export function formatKeymapExtension(
  cellId: CellId,
  updateCellCode: CellActions["updateCellCode"],
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
