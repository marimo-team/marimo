/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { useAtomValue, useSetAtom, useStore } from "jotai";
import { mergeProps, useFocusWithin, useKeyboard } from "react-aria";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { notebookAtom, useCellActions } from "@/core/cells/cells";
import { useSetLastFocusedCellId } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import { hotkeysAtom, keymapPresetAtom } from "@/core/config/config";
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { parseShortcut } from "@/core/hotkeys/shortcuts";
import { saveCellConfig } from "@/core/network/requests";
import { useSaveNotebook } from "@/core/saving/save-component";
import { derefNotNull } from "@/utils/dereference";
import { Events } from "@/utils/events";
import type { CellActionsDropdownHandle } from "../cell/cell-actions";
import { useRunCell } from "../cell/useRunCells";
import { useCellClipboard } from "./clipboard";
import { focusCell, focusCellEditor } from "./focus-utils";
import { temporarilyShownCodeAtom } from "./state";

interface HotkeyHandler {
  handle: (cellId: CellId) => boolean;
  bulkHandle: (cellIds: CellId[]) => boolean;
}

/**
 * Wraps a hotkey handler to support bulk handling.
 *
 * If a handler fails mid-way, the bulk handling will stop.
 */
function supportBulkHandle(handler: HotkeyHandler["handle"]): HotkeyHandler {
  return {
    handle: (cellId) => {
      return handler(cellId);
    },
    bulkHandle: (cellIds) => {
      let success = true;
      try {
        for (const cellId of cellIds) {
          success = success && handler(cellId);
        }
        return success;
      } catch {
        return false;
      }
    },
  };
}

function useCellFocusProps(cellId: CellId) {
  const setLastFocusedCellId = useSetLastFocusedCellId();
  const actions = useCellActions();
  const setTemporarilyShownCode = useSetAtom(temporarilyShownCodeAtom);

  // This occurs at the cell level and descedants.
  const { focusWithinProps } = useFocusWithin({
    onFocusWithin: () => {
      // On focus, set the last focused cell id.
      setLastFocusedCellId(cellId);
    },
    onBlurWithin: () => {
      // On blur, hide the code if it was temporarily shown.
      setTemporarilyShownCode(false);
      actions.markTouched({ cellId });
    },
  });

  return focusWithinProps;
}

/**
 * Props for cell keyboard navigation,
 * to manage focus and selection.
 *
 * Handles both keyboard and mouse navigation.
 *
 * Includes some relevant Jupyter command mode:
 * https://jupyter-notebook.readthedocs.io/en/stable/examples/Notebook/Notebook%20Basics.html#Keyboard-Navigation
 */
export function useCellNavigationProps(
  cellId: CellId,
  {
    canMoveX,
    editorView,
    cellActionDropdownRef,
  }: {
    canMoveX: boolean;
    editorView: React.RefObject<EditorView | null>;
    cellActionDropdownRef: React.RefObject<CellActionsDropdownHandle | null>;
  },
) {
  const { saveOrNameNotebook } = useSaveNotebook();
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);
  const actions = useCellActions();
  const store = useStore();
  const setTemporarilyShownCode = useSetAtom(temporarilyShownCodeAtom);
  const runCell = useRunCell(cellId);
  const keymapPreset = useAtomValue(keymapPresetAtom);
  const { copyCell, pasteCell } = useCellClipboard();
  const hotkeys = useAtomValue(hotkeysAtom);

  const isShortcutPressed = (
    shortcut: HotkeyAction,
    evt: React.KeyboardEvent<HTMLElement>,
  ) => parseShortcut(hotkeys.getHotkey(shortcut).key)(evt.nativeEvent || evt);

  // Callbacks occur at the cell level and descedants.
  const focusWithinProps = useCellFocusProps(cellId);

  const { keyboardProps } = useKeyboard({
    onKeyDown: (evt) => {
      // Event came from an input, do nothing.
      if (Events.fromInput(evt)) {
        evt.continuePropagation();
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

      // Enter will focus the cell editor.
      if (evt.key === "Enter" && !Events.hasModifier(evt)) {
        setTemporarilyShownCode(true);
        focusCellEditor(store, cellId);
        // Prevent default to prevent an new line from being created.
        evt.preventDefault();
        return;
      }

      // Saving
      if (evt.key === "s" && !Events.hasModifier(evt)) {
        saveOrNameNotebook();
        return;
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
        if (evt.key === "i" && !Events.hasModifier(evt)) {
          setTemporarilyShownCode(true);
          focusCellEditor(store, cellId);
          evt.preventDefault();
          return;
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

      // Shortcuts
      const shortcuts: Partial<
        Record<HotkeyAction, HotkeyHandler["handle"] | HotkeyHandler>
      > = {
        // Cell actions
        "cell.run": () => {
          runCell();
          return true;
        },
        "cell.runAndNewBelow": (cellId) => {
          runCell();
          actions.moveToNextCell({ cellId, before: false });
          return true;
        },
        "cell.runAndNewAbove": () => {
          runCell();
          actions.moveToNextCell({ cellId, before: true });
          return true;
        },
        "cell.createAbove": (cellId) => {
          actions.createNewCell({ cellId, before: true });
          return true;
        },
        "cell.createBelow": (cellId) => {
          actions.createNewCell({ cellId, before: false });
          return true;
        },
        "cell.moveUp": (cellId) => {
          actions.moveCell({ cellId, before: true });
          return true;
        },
        "cell.moveDown": (cellId) => {
          actions.moveCell({ cellId, before: false });
          return true;
        },
        "cell.moveLeft": (cellId) => {
          if (canMoveX) {
            actions.moveCell({ cellId, direction: "left" });
            return true;
          }
          return false;
        },
        "cell.moveRight": (cellId) => {
          if (canMoveX) {
            actions.moveCell({ cellId, direction: "right" });
            return true;
          }
          return false;
        },
        "cell.hideCode": supportBulkHandle((cellId) => {
          const cellConfig = store.get(notebookAtom).cellData[cellId]?.config;
          if (!cellConfig) {
            return false;
          }
          const nextHideCode = !cellConfig.hide_code;
          // Fire-and-forget
          void saveCellConfig({
            configs: { [cellId]: { hide_code: nextHideCode } },
          });
          actions.updateCellConfig({
            cellId,
            config: { hide_code: nextHideCode },
          });
          actions.focusCell({ cellId, before: false });
          if (nextHideCode) {
            // Move focus from the editor to the cell
            editorView.current?.contentDOM.blur();
            focusCell(cellId);
          } else {
            focusCellEditor(store, cellId);
          }
          return true;
        }),
        "cell.focusDown": (cellId) => {
          actions.focusCell({ cellId, before: false });
          return true;
        },
        "cell.focusUp": (cellId) => {
          actions.focusCell({ cellId, before: true });
          return true;
        },
        "cell.sendToBottom": (cellId) => {
          actions.sendToBottom({ cellId });
          return true;
        },
        "cell.sendToTop": (cellId) => {
          actions.sendToTop({ cellId });
          return true;
        },
        "cell.aiCompletion": (cellId) => {
          let closed = false;
          setAiCompletionCell((v) => {
            // Toggle close
            if (v?.cellId === cellId) {
              closed = true;
              return null;
            }
            return { cellId };
          });
          if (closed) {
            derefNotNull(editorView).focus();
          }
          return true;
        },
        "cell.cellActions": () => {
          cellActionDropdownRef.current?.toggle();
          return true;
        },

        // Command mode
        "command.copyCell": () => {
          copyCell(cellId);
          return true;
        },
        "command.pasteCell": () => {
          pasteCell(cellId);
          return true;
        },
        "command.createCellBefore": (cellId) => {
          if (Events.hasModifier(evt)) {
            return false;
          }
          actions.createNewCell({ cellId, before: true, autoFocus: true });
          return true;
        },
        "command.createCellAfter": (cellId) => {
          if (Events.hasModifier(evt)) {
            return false;
          }
          actions.createNewCell({ cellId, before: false, autoFocus: true });
          return true;
        },
      };

      // Handle the shortcut
      for (const [shortcut, handler] of Object.entries(shortcuts)) {
        if (isShortcutPressed(shortcut as HotkeyAction, evt)) {
          if (handler instanceof Function) {
            const success = handler(cellId);
            if (success) {
              evt.preventDefault();
              return;
            }
          } else {
            // TODO: Support bulk handling once we have multi-select.
            const success = handler.handle(cellId);
            if (success) {
              evt.preventDefault();
              return;
            }
          }
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

  const { keyboardProps } = useKeyboard({
    onKeyDown: (evt) => {
      if (evt.key === "Escape") {
        setTemporarilyShownCode(false);
        focusCell(cellId);
      }

      evt.continuePropagation();
    },
  });

  return keyboardProps;
}
