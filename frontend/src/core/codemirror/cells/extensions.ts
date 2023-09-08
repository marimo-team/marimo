/* Copyright 2023 Marimo. All rights reserved. */
import { HOTKEYS } from "@/core/hotkeys/hotkeys";
import { KeyBinding, keymap } from "@codemirror/view";
import { EditorView } from "codemirror";
import { CellId } from "@/core/model/ids";
import { Extension, Prec } from "@codemirror/state";
import { formatKeymapExtension } from "../extensions";
import { CellActions } from "@/core/state/cells";

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
}

/**
 * Extensions for cell movement
 */
export function cellMovementBundle(
  cellId: CellId,
  callbacks: MovementCallbacks
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
  } = callbacks;

  const hotkeys: KeyBinding[] = [
    {
      key: HOTKEYS.getHotkey("cell.run").key,
      preventDefault: true,
      run: () => {
        onRun();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.runAndNewBelow").key,
      preventDefault: true,
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
      run: () => {
        moveDown();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.moveUp").key,
      preventDefault: true,
      run: () => {
        moveUp();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.focusDown").key,
      preventDefault: true,
      run: () => {
        focusDown();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.focusUp").key,
      preventDefault: true,
      run: () => {
        focusUp();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.sendToBottom").key,
      preventDefault: true,
      run: () => {
        sendToBottom({ cellId });
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.sendToTop").key,
      preventDefault: true,
      run: () => {
        sendToTop({ cellId });
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.createAbove").key,
      preventDefault: true,
      run: (ev) => {
        ev.contentDOM.blur();
        createAbove();
        return true;
      },
    },
    {
      key: HOTKEYS.getHotkey("cell.createBelow").key,
      preventDefault: true,
      run: (ev) => {
        ev.contentDOM.blur();
        createBelow();
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
  callbacks: CodeCallbacks
): Extension[] {
  const { updateCellCode } = callbacks;

  const onChangePlugin = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      const nextCode = update.state.doc.toString();
      updateCellCode({ cellId, code: nextCode, formattingChange: false });
    }
  });

  return [onChangePlugin, formatKeymapExtension(cellId, updateCellCode)];
}
