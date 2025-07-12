/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useSetAtom } from "jotai";
import { mergeProps, useFocusWithin, useKeyboard } from "react-aria";
import { useCellActions } from "@/core/cells/cells";
import { useSetLastFocusedCellId } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import { keymapPresetAtom } from "@/core/config/config";
import { Events } from "@/utils/events";
import { useCellFocusManager } from "./focus-manager";
import { temporarilyShownCodeAtom } from "./state";

/**
 * Props for cell keyboard navigation,
 * to manage focus and selection.
 *
 * Handles both keyboard and mouse navigation.
 */
export function useCellNavigationProps(cellId: CellId) {
  const setLastFocusedCellId = useSetLastFocusedCellId();
  const actions = useCellActions();
  const setTemporarilyShownCode = useSetAtom(temporarilyShownCodeAtom);
  const focusManager = useCellFocusManager();
  const keymapPreset = useAtomValue(keymapPresetAtom);

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
      // Came from an input, do nothing.
      if (Events.fromInput(evt)) {
        return;
      }

      // Down arrow moves to the next cell.
      if (evt.key === "ArrowDown") {
        actions.moveToNextCell({ cellId, before: false, noCreate: true });
      }
      // Up arrow moves to the previous cell.
      if (evt.key === "ArrowUp") {
        actions.moveToNextCell({ cellId, before: true, noCreate: true });
      }
      // Enter will focus the cell editor.
      if (evt.key === "Enter") {
        setTemporarilyShownCode(true);
        focusManager.focusCellEditor(cellId);
        // Prevent default to prevent an new line from being created.
        evt.preventDefault();
      }

      // j/k movement in vim mode.
      if (keymapPreset === "vim") {
        if (evt.key === "j") {
          actions.moveToNextCell({ cellId, before: false, noCreate: true });
        }
        if (evt.key === "k") {
          actions.moveToNextCell({ cellId, before: true, noCreate: true });
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
