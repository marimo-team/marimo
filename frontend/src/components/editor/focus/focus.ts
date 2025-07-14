/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useSetAtom } from "jotai";
import { mergeProps, useFocusWithin, useKeyboard } from "react-aria";
import { useCellActions } from "@/core/cells/cells";
import { useSetLastFocusedCellId } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import { hotkeysAtom, keymapPresetAtom } from "@/core/config/config";
import { useSaveNotebook } from "@/core/saving/save-component";
import { Events } from "@/utils/events";
import { useRunCell } from "../cell/useRunCells";
import { useCellClipboard } from "./clipboard";
import { useCellFocusManager } from "./focus-manager";
import { temporarilyShownCodeAtom } from "./state";

/**
 * Props for cell keyboard navigation,
 * to manage focus and selection.
 *
 * Handles both keyboard and mouse navigation.
 *
 * Includes some relevant Jupyter command mode:
 * https://jupyter-notebook.readthedocs.io/en/stable/examples/Notebook/Notebook%20Basics.html#Keyboard-Navigation
 */
export function useCellNavigationProps(cellId: CellId) {
  const setLastFocusedCellId = useSetLastFocusedCellId();
  const { saveOrNameNotebook } = useSaveNotebook();
  const actions = useCellActions();
  const setTemporarilyShownCode = useSetAtom(temporarilyShownCodeAtom);
  const focusManager = useCellFocusManager();
  const runCell = useRunCell(cellId);
  const keymapPreset = useAtomValue(keymapPresetAtom);
  const hotkeys = useAtomValue(hotkeysAtom);
  const { copyCell, pasteCell } = useCellClipboard();

  // This occurs at the cell level and descedants.
  const { focusWithinProps } = useFocusWithin({
    onFocusWithin: () => {
      // On focus, set the last focused cell id.
      setLastFocusedCellId(cellId);
    },
    onBlurWithin: () => {
      // On blur, hide the code if it was temporarily shown.
      setTemporarilyShownCode(false);
    },
  });

  const { keyboardProps } = useKeyboard({
    onKeyDown: (evt) => {
      // Event came from an input, do nothing.
      if (Events.fromInput(evt)) {
        evt.continuePropagation();
        return;
      }

      // Copy cell
      if (evt.key === "c") {
        copyCell(cellId);
        evt.preventDefault();
        return;
      }

      // Paste cell
      if (evt.key === "v") {
        pasteCell(cellId);
        evt.preventDefault();
        return;
      }

      // Mod+Up/Down moves to the top/bottom of the notebook.
      if (Events.isMetaOrCtrl(evt)) {
        if (evt.key === "ArrowUp") {
          actions.focusTopCell();
          return;
        }
        if (evt.key === "ArrowDown") {
          actions.focusBottomCell();
          return;
        }
      }
      // Down arrow moves to the next cell.
      if (evt.key === "ArrowDown" && !Events.hasModifier(evt)) {
        actions.focusCell({ cellId, before: false });
        return;
      }
      // Up arrow moves to the previous cell.
      if (evt.key === "ArrowUp" && !Events.hasModifier(evt)) {
        actions.focusCell({ cellId, before: true });
        return;
      }

      // Shift-Enter will run the cell and move to the next cell.
      if (evt.key === "Enter" && evt.shiftKey) {
        runCell();
        actions.focusCell({ cellId, before: false });
        evt.preventDefault();
        return;
      }

      // Enter will focus the cell editor.
      if (evt.key === "Enter") {
        setTemporarilyShownCode(true);
        focusManager.focusCellEditor(cellId);
        // Prevent default to prevent an new line from being created.
        evt.preventDefault();
        return;
      }

      // Saving
      if (evt.key === "s") {
        saveOrNameNotebook();
        return;
      }

      // Create cell before
      if (
        hotkeys.getHotkey("command.createCellBefore").key &&
        !Events.hasModifier(evt)
      ) {
        actions.createNewCell({
          cellId,
          before: true,
          autoFocus: true,
        });
      }
      // Create cell after
      if (
        hotkeys.getHotkey("command.createCellAfter").key &&
        !Events.hasModifier(evt)
      ) {
        actions.createNewCell({
          cellId,
          before: false,
          autoFocus: true,
        });
      }

      // j/k movement in vim mode.
      if (keymapPreset === "vim") {
        if (evt.key === "j" && !Events.hasModifier(evt)) {
          actions.focusCell({ cellId, before: false });
          return;
        }
        if (evt.key === "k" && !Events.hasModifier(evt)) {
          actions.focusCell({ cellId, before: true });
          return;
        }
      }

      evt.continuePropagation();
    },
  });

  return mergeProps(focusWithinProps, keyboardProps);
}

/**
 * Props for cell editor navigation,
 * to manage focus and selection.
 *
 * Handles both keyboard and mouse navigation.
 */
export function useCellEditorNavigationProps(cellId: CellId) {
  const setTemporarilyShownCode = useSetAtom(temporarilyShownCodeAtom);
  const focusManager = useCellFocusManager();

  const { keyboardProps } = useKeyboard({
    onKeyDown: (evt) => {
      if (evt.key === "Escape") {
        setTemporarilyShownCode(false);
        focusManager.focusCell(cellId);
      }

      evt.continuePropagation();
    },
  });

  return keyboardProps;
}
