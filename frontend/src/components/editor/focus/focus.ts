/* Copyright 2024 Marimo. All rights reserved. */

import { useSetAtom } from "jotai";
import { mergeProps, useFocus, useKeyboard } from "react-aria";
import { useCellActions } from "@/core/cells/cells";
import { useSetLastFocusedCellId } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
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

  const { focusProps } = useFocus({
    onFocus: () => {
      // On focus, set the last focused cell id.
      setLastFocusedCellId(cellId);
    },
    onBlur: () => {
      // On blur, hide the code if it was temporarily shown.
      setTemporarilyShownCode(false);
    },
  });

  const { keyboardProps } = useKeyboard({
    onKeyDown: (evt) => {
      // Down arrow moves to the next cell.
      if (evt.key === "ArrowDown") {
        if (evt && Events.fromInput(evt)) {
          return;
        }
        actions.moveToNextCell({ cellId, before: false, noCreate: true });
      }
      // Up arrow moves to the previous cell.
      if (evt.key === "ArrowUp") {
        if (evt && Events.fromInput(evt)) {
          return;
        }
        actions.moveToNextCell({ cellId, before: true, noCreate: true });
      }
      // Enter will focus the cell editor.
      if (evt.key === "Enter") {
        if (evt && Events.fromInput(evt)) {
          return;
        }
        setTemporarilyShownCode(true);
        focusManager.focusCellEditor(cellId);
      }

      evt.continuePropagation();
    },
  });

  return mergeProps(focusProps, keyboardProps);
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
