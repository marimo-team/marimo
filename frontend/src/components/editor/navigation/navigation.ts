/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { useAtomValue, useSetAtom, useStore } from "jotai";
import { mergeProps, useFocusWithin, useKeyboard } from "react-aria";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { cellIdsAtom, notebookAtom, useCellActions } from "@/core/cells/cells";
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
import { useRunCells } from "../cell/useRunCells";
import { useCellClipboard } from "./clipboard";
import { focusCell, focusCellEditor } from "./focus-utils";
import {
  getSelectedCells,
  useCellSelectionActions,
  useIsCellSelected,
} from "./selection";
import { temporarilyShownCodeAtom } from "./state";

interface HotkeyHandler {
  handle: (cellId: CellId) => boolean;
  bulkHandle: (cellIds: CellId[]) => boolean;
}

/**
 * Wraps a hotkey handler to support bulk handling.
 * If a handler fails mid-way, the bulk handling will stop.
 *
 * Use this utility if the bulk handler is the same as handling each cell individually.
 */
function addBulkHandler(handler: HotkeyHandler["handle"]): HotkeyHandler {
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

/**
 * Wraps a bulk handler to support single-cell handling.
 *
 * Use this utility if the single-cell handler is the same as a single-cell bulk handler.
 */
function addSingleHandler(handler: HotkeyHandler["bulkHandle"]): HotkeyHandler {
  return {
    handle: (cellId) => {
      return handler([cellId]);
    },
    bulkHandle: (cellIds) => {
      return handler(cellIds);
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
  const runCells = useRunCells();
  const keymapPreset = useAtomValue(keymapPresetAtom);
  const { copyCells, pasteAtCell } = useCellClipboard();
  const selectionActions = useCellSelectionActions();
  const isSelected = useIsCellSelected(cellId);

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
          selectionActions.clear();
          return;
        }
        if (evt.key === "ArrowDown") {
          actions.focusBottomCell();
          selectionActions.clear();
          return;
        }
      }

      const handleSelectUp = () => {
        // Select self
        const allCellIds = store.get(cellIdsAtom);
        selectionActions.extend({ cellId, allCellIds });
        // Select to where focus is going
        const beforeCellId = allCellIds.findWithId(cellId).before(cellId);
        if (beforeCellId) {
          selectionActions.extend({ cellId: beforeCellId, allCellIds });
        }
        // Focus the cell
        actions.focusCell({ cellId, before: true });
        return;
      };
      const handleSelectDown = () => {
        // Select self
        const allCellIds = store.get(cellIdsAtom);
        selectionActions.extend({ cellId, allCellIds });
        // Select to where focus is going
        const afterCellId = allCellIds.findWithId(cellId).after(cellId);
        if (afterCellId) {
          selectionActions.extend({ cellId: afterCellId, allCellIds });
        }
        // Focus the cell
        actions.focusCell({ cellId, before: false });
        return;
      };
      const handleMoveUp = () => {
        actions.focusCell({ cellId, before: true });
        selectionActions.clear();
        return;
      };
      const handleMoveDown = () => {
        actions.focusCell({ cellId, before: false });
        selectionActions.clear();
        return;
      };

      // --- Selection ---
      // Shift-Up/Down extends the selection.
      if (evt.key === "ArrowUp" && evt.shiftKey) {
        handleSelectUp();
        return;
      }
      if (evt.key === "ArrowDown" && evt.shiftKey) {
        handleSelectDown();
        return;
      }
      if (evt.key === "Escape") {
        // Clear selection on Esc
        selectionActions.clear();
        return;
      }

      // Enter will focus the cell editor.
      if (evt.key === "Enter" && !Events.hasModifier(evt)) {
        setTemporarilyShownCode(true);
        focusCellEditor(store, cellId);
        selectionActions.clear();
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
          handleMoveDown();
          return;
        }
        if (evt.key === "k" && !Events.hasModifier(evt)) {
          handleMoveUp();
          return;
        }

        // Shift-j/k extends the selection.
        if (evt.key === "J" && evt.shiftKey) {
          handleSelectDown();
          return;
        }
        if (evt.key === "K" && evt.shiftKey) {
          handleSelectUp();
          return;
        }
      }

      // Down arrow moves to the next cell.
      if (evt.key === "ArrowDown" && !Events.hasModifier(evt)) {
        handleMoveDown();
        return;
      }
      // Up arrow moves to the previous cell.
      if (evt.key === "ArrowUp" && !Events.hasModifier(evt)) {
        handleMoveUp();
        return;
      }

      // Shortcuts
      const shortcuts: Partial<
        Record<HotkeyAction, HotkeyHandler["handle"] | HotkeyHandler>
      > = {
        // Cell actions
        "cell.run": addSingleHandler((cellIds) => {
          runCells(cellIds);
          return true;
        }),
        "cell.runAndNewBelow": addSingleHandler((cellIds) => {
          runCells(cellIds);
          const lastCellId = cellIds[cellIds.length - 1];
          actions.moveToNextCell({ cellId: lastCellId, before: false });
          return true;
        }),
        "cell.runAndNewAbove": addSingleHandler((cellIds) => {
          runCells(cellIds);
          const firstCellId = cellIds[0];
          actions.moveToNextCell({ cellId: firstCellId, before: true });
          return true;
        }),
        "cell.createAbove": (cellId) => {
          actions.createNewCell({ cellId, before: true });
          return true;
        },
        "cell.createBelow": (cellId) => {
          actions.createNewCell({ cellId, before: false });
          return true;
        },
        "cell.moveUp": addSingleHandler((cellIds) => {
          // If moving up, make sure the first cell is not at the top of the notebook
          const firstCellId = cellIds[0];
          const notebook = store.get(notebookAtom);
          const isFirst =
            notebook.cellIds.findWithId(firstCellId).first() === firstCellId;
          if (isFirst) {
            return false;
          }

          cellIds.forEach((cellId) => {
            actions.moveCell({ cellId, before: true });
          });
          return true;
        }),
        "cell.moveDown": addSingleHandler((cellIds) => {
          // If moving down, make sure the last cell is not at the bottom of the notebook
          const lastCellId = cellIds[cellIds.length - 1];
          const notebook = store.get(notebookAtom);
          const isLast =
            notebook.cellIds.findWithId(lastCellId).last() === lastCellId;
          if (isLast) {
            return false;
          }

          // Move cells in the appropriate order to maintain relative positions
          [...cellIds].reverse().forEach((cellId) => {
            actions.moveCell({ cellId, before: false });
          });
          return true;
        }),
        "cell.moveLeft": addBulkHandler((cellId) => {
          if (canMoveX) {
            actions.moveCell({ cellId, direction: "left" });
            return true;
          }
          return false;
        }),
        "cell.moveRight": addBulkHandler((cellId) => {
          if (canMoveX) {
            actions.moveCell({ cellId, direction: "right" });
            return true;
          }
          return false;
        }),
        "cell.hideCode": addBulkHandler((cellId) => {
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
        "cell.sendToBottom": addSingleHandler((cellIds) => {
          cellIds.forEach((cellId) => {
            actions.sendToBottom({ cellId });
          });
          return true;
        }),
        "cell.sendToTop": addSingleHandler((cellIds) => {
          // Send in reverse order to maintain relative positions
          [...cellIds].reverse().forEach((cellId) => {
            actions.sendToTop({ cellId });
          });
          return true;
        }),
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
        "command.copyCell": addSingleHandler((cellIds) => {
          copyCells(cellIds);
          return true;
        }),
        "command.pasteCell": (cellIds) => {
          pasteAtCell(cellIds);
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

      const selectedCells = getSelectedCells(store);

      // Handle the shortcut
      for (const [shortcut, handler] of Object.entries(shortcuts)) {
        if (isShortcutPressed(shortcut as HotkeyAction, evt)) {
          // If the handler is a function, it's a single-cell handler
          // and we only operate on the currently focused cell.
          if (handler instanceof Function) {
            const success = handler(cellId);
            if (success) {
              evt.preventDefault();
              return;
            }
          } else {
            // If the handler is an object, it's supports bulk handling.
            // If we have multiple cells selected, use the bulk handler,
            // otherwise use the single-cell handler on the focused cell.
            const success =
              selectedCells.size >= 2
                ? handler.bulkHandle([...selectedCells])
                : handler.handle(cellId);
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

  return mergeProps(focusWithinProps, keyboardProps, {
    "data-selected": isSelected,
    className:
      "data-[selected=true]:ring-1 data-[selected=true]:ring-[var(--blue-8)] data-[selected=true]:ring-offset-1",
  });
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
