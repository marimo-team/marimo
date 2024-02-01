/* Copyright 2024 Marimo. All rights reserved. */
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import { EditorView, KeyBinding, keymap } from "@codemirror/view";
import { CellId, HTMLCellId } from "@/core/cells/ids";
import { Extension, Prec } from "@codemirror/state";
import { formatKeymapExtension } from "../extensions";
import { CellActions } from "@/core/cells/cells";
import { getEditorCodeAsPython } from "../language/utils";
import { formattingChangeEffect } from "../format";
import { closeCompletion, completionStatus } from "@codemirror/autocomplete";
import { isAtEndOfEditor, isAtStartOfEditor } from "../utils";

export interface MovementCallbacks
  extends Pick<CellActions, "sendToTop" | "sendToBottom" | "moveToNextCell"> {
  onRun: () => void;
  deleteCell: () => void;
  createAbove: () => void;
  createBelow: () => void;
  moveUp: () => void;
  moveDown: () => void;
  focusUp: () => void;
  focusDown: () => void;
  toggleHideCode: () => boolean;
}

/**
 * Extensions for cell movement
 */
export function cellMovementBundle(
  cellId: CellId,
  callbacks: MovementCallbacks,
): Extension[] {
  const {
    onRun,
    deleteCell,
    createAbove,
    createBelow,
    moveUp,
    moveDown,
    focusUp,
    focusDown,
    sendToTop,
    sendToBottom,
    moveToNextCell,
    toggleHideCode,
  } = callbacks;

  const hotkeys: KeyBinding[] = [
    {
      key: HOTKEYS.getHotkey("cell.run").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        onRun();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.runAndNewBelow").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        onRun();
        ev.contentDOM.blur();
        moveToNextCell({ cellId, before: false });
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.runAndNewAbove").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        onRun();
        ev.contentDOM.blur();
        moveToNextCell({ cellId, before: true });
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.delete").key,
      preventDefault: true,
      stopPropagation: true,
      run: (cm) => {
        // Cannot delete non-empty cells for safety
        if (cm.state.doc.length === 0) {
          deleteCell();
        }
        // shortcuts.delete (shift-backspace) overlaps with
        // defaultKeymap's deleteCharBackward (backspace); we don't want
        // shift-backspace to trigger character deletion, because otherwise
        // users might accidentally delete their whole notebook if they
        // absent-mindedly held these keys. That's why we always return true.
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.moveDown").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        moveDown();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.moveUp").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        moveUp();
        return true;
      },
    },
    {
      key: "ArrowUp",
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        // Skip if we are in the middle of an autocompletion
        const hasAutocomplete = completionStatus(ev.state);
        if (hasAutocomplete) {
          return false;
        }

        if (isAtStartOfEditor(ev)) {
          focusUp();
          return true;
        }
        return false;
      },
    },
    {
      key: "ArrowDown",
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        // Skip if we are in the middle of an autocompletion
        const hasAutocomplete = completionStatus(ev.state);
        if (hasAutocomplete) {
          return false;
        }

        if (isAtEndOfEditor(ev)) {
          focusDown();
          return true;
        }
        return false;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.focusDown").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        focusDown();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.focusUp").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        focusUp();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.sendToBottom").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        sendToBottom({ cellId });
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.sendToTop").key,
      preventDefault: true,
      stopPropagation: true,
      run: () => {
        sendToTop({ cellId });
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.createAbove").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        ev.contentDOM.blur();
        createAbove();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.createBelow").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        ev.contentDOM.blur();
        createBelow();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.hideCode").key,
      preventDefault: true,
      stopPropagation: true,
      run: (ev) => {
        const isHidden = toggleHideCode();
        closeCompletion(ev);
        // If we are newly hidden, blur the editor
        if (isHidden) {
          ev.contentDOM.blur();
          // Focus on the parent element
          document.getElementById(HTMLCellId.create(cellId))?.focus();
        } else {
          ev.contentDOM.focus();
        }
        return true;
      },
    },
  ];

  // Highest priority so that we can override the default keymap
  return [Prec.highest(keymap.of(hotkeys))];
}

export interface CodeCallbacks {
  updateCellCode: CellActions["updateCellCode"];
}

/**
 * Extensions for cell code editing
 */
export function cellCodeEditingBundle(
  cellId: CellId,
  callbacks: CodeCallbacks,
): Extension[] {
  const { updateCellCode } = callbacks;

  const onChangePlugin = EditorView.updateListener.of((update) => {
    // Check if the doc update was a formatting change
    // e.g. changing from python to markdown
    const isFormattingChange = update.transactions.some((tr) =>
      tr.effects.some((effect) => effect.is(formattingChangeEffect)),
    );
    if (update.docChanged) {
      const nextCode = getEditorCodeAsPython(update.view);
      updateCellCode({
        cellId,
        code: nextCode,
        formattingChange: isFormattingChange,
      });
    }
  });

  return [onChangePlugin, formatKeymapExtension(cellId, updateCellCode)];
}
