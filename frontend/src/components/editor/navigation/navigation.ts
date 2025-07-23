/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { useAtomValue, useSetAtom, useStore } from "jotai";
import { mergeProps, useFocusWithin, useKeyboard } from "react-aria";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { cellIdsAtom, notebookAtom, useCellActions } from "@/core/cells/cells";
import { useCellFocusActions } from "@/core/cells/focus";
import type { CellId } from "@/core/cells/ids";
import { usePendingDeleteService } from "@/core/cells/pending-delete-service";
import {
  hotkeysAtom,
  keymapPresetAtom,
  userConfigAtom,
} from "@/core/config/config";
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { parseShortcut } from "@/core/hotkeys/shortcuts";
import { saveCellConfig } from "@/core/network/requests";
import { useSaveNotebook } from "@/core/saving/save-component";
import { Events } from "@/utils/events";
import type { CellActionsDropdownHandle } from "../cell/cell-actions";
import { useDeleteManyCellsCallback } from "../cell/useDeleteCell";
import { useRunCells } from "../cell/useRunCells";
import { useCellClipboard } from "./clipboard";
import { focusCell, focusCellEditor } from "./focus-utils";
import {
  getSelectedCells,
  useCellSelectionActions,
  useIsCellSelected,
} from "./selection";
import { temporarilyShownCodeAtom } from "./state";
import { handleVimKeybinding } from "./vim-bindings";

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
  const focusActions = useCellFocusActions();
  const actions = useCellActions();
  const setTemporarilyShownCode = useSetAtom(temporarilyShownCodeAtom);

  // This occurs at the cell level and descedants.
  const { focusWithinProps } = useFocusWithin({
    onFocusWithin: () => {
      // On focus, set the last focused cell id.
      focusActions.focusCell({ cellId });
    },
    onBlurWithin: () => {
      // On blur, hide the code if it was temporarily shown.
      setTemporarilyShownCode(false);
      actions.markTouched({ cellId });
      focusActions.blurCell();
    },
  });

  return focusWithinProps;
}

type KeymapHandlers = Record<string, () => boolean>;

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
  const rawSelectionActions = useCellSelectionActions();
  const isSelected = useIsCellSelected(cellId);
  const pendingDeleteService = usePendingDeleteService();
  const deleteCells = useDeleteManyCellsCallback();
  const userConfig = useAtomValue(userConfigAtom);

  // Wrap selection actions to clear pending cells on any selection change
  const selectionActions = {
    clear: () => {
      pendingDeleteService.clear();
      rawSelectionActions.clear();
    },
    extend: (args: Parameters<typeof rawSelectionActions.extend>[0]) => {
      pendingDeleteService.clear();
      rawSelectionActions.extend(args);
    },
    select: (args: Parameters<typeof rawSelectionActions.select>[0]) => {
      pendingDeleteService.clear();
      rawSelectionActions.select(args);
    },
  };

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

      const keymaps = {
        // Move to the top of the notebook.
        "Mod+ArrowUp": () => {
          actions.focusTopCell();
          selectionActions.clear();
          return true;
        },
        // Move to the bottom of the notebook.
        "Mod+ArrowDown": () => {
          actions.focusBottomCell();
          selectionActions.clear();
          return true;
        },
        // Move up
        ArrowUp: () => {
          actions.focusCell({ cellId, where: "before" });
          selectionActions.clear();
          return true;
        },
        // Move down
        ArrowDown: () => {
          actions.focusCell({ cellId, where: "after" });
          selectionActions.clear();
          return true;
        },
        // Select up
        "Shift+ArrowUp": () => {
          // Select self
          const allCellIds = store.get(cellIdsAtom);
          selectionActions.extend({ cellId, allCellIds });
          // Select to where focus is going
          const beforeCellId = allCellIds.findWithId(cellId).before(cellId);
          if (beforeCellId) {
            selectionActions.extend({ cellId: beforeCellId, allCellIds });
          }
          // Focus the cell
          actions.focusCell({ cellId, where: "before" });
          return true;
        },
        // Select down
        "Shift+ArrowDown": () => {
          // Select self
          const allCellIds = store.get(cellIdsAtom);
          selectionActions.extend({ cellId, allCellIds });
          // Select to where focus is going
          const afterCellId = allCellIds.findWithId(cellId).after(cellId);
          if (afterCellId) {
            selectionActions.extend({ cellId: afterCellId, allCellIds });
          }
          // Focus the cell
          actions.focusCell({ cellId, where: "after" });
          return true;
        },
        // Clear selection
        Escape: () => {
          if (isSelected) {
            selectionActions.clear();
            return true;
          }
          return false;
        },
        // Enter will focus the cell editor.
        Enter: () => {
          setTemporarilyShownCode(true);
          focusCellEditor(store, cellId);
          selectionActions.clear();
          return true;
        },
        // Command mode: Saving
        s: () => {
          saveOrNameNotebook();
          return true;
        },
      } satisfies KeymapHandlers;

      // Handle keymaps.
      for (const [key, handler] of Object.entries(keymaps)) {
        if (parseShortcut(key)(evt)) {
          const success = handler();
          if (success) {
            evt.preventDefault();
            return;
          }
        }
      }

      // Shortcuts
      const shortcuts = {
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
        "cell.hideCode": addSingleHandler((cellIds) => {
          // Get the cell configs
          const cellConfigs = cellIds.map((cellId) => {
            const cellConfig = store.get(notebookAtom).cellData[cellId]?.config;
            if (!cellConfig) {
              return null;
            }
            return cellConfig;
          });

          // Toggle to the same value for all cells
          const nextHideCode = !cellConfigs.every(
            (config) => config?.hide_code,
          );

          // Fire-and-forget
          void saveCellConfig({
            configs: Object.fromEntries(
              cellIds.map((cellId) => [cellId, { hide_code: nextHideCode }]),
            ),
          });

          for (const cellId of cellIds) {
            actions.updateCellConfig({
              cellId,
              config: { hide_code: nextHideCode },
            });
          }

          // Only focus if it is a single cell
          if (cellIds.length === 1) {
            const cellId = cellIds[0];
            actions.focusCell({ cellId, where: "after" });
            if (nextHideCode) {
              // Move focus from the editor to the cell
              editorView.current?.contentDOM.blur();
              focusCell(cellId);
            } else {
              focusCellEditor(store, cellId);
            }
          }

          return true;
        }),
        "cell.focusDown": (cellId) => {
          actions.focusCell({ cellId, where: "after" });
          return true;
        },
        "cell.focusUp": (cellId) => {
          actions.focusCell({ cellId, where: "before" });
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
            editorView.current?.focus();
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
        "cell.delete": () => {
          // Only handle if destructive_delete is enabled
          if (!userConfig.keymap.destructive_delete) {
            return false;
          }

          const cellIds =
            selectedCells.size >= 2 ? [...selectedCells] : [cellId];

          // Cannot delete running cells
          const notebook = store.get(notebookAtom);
          const hasRunningCell = cellIds.some((id) => {
            const { status } = notebook.cellRuntime[id];
            return status === "running" || status === "queued";
          });

          if (hasRunningCell) {
            return false;
          }

          // First keymap sets pending, second deletes
          if (pendingDeleteService.idle) {
            pendingDeleteService.submit(cellIds);
            return true;
          }

          // user repeated keymap
          deleteCells({ cellIds });
          pendingDeleteService.clear();
          return true;
        },
      } satisfies Partial<
        Record<HotkeyAction, HotkeyHandler["handle"] | HotkeyHandler>
      >;

      const selectedCells = getSelectedCells(store);

      // Keymaps when using vim.
      if (
        keymapPreset === "vim" &&
        handleVimKeybinding(evt.nativeEvent || evt, {
          j: keymaps.ArrowDown,
          k: keymaps.ArrowUp,
          i: keymaps.Enter,
          "shift+j": keymaps["Shift+ArrowDown"],
          "shift+k": keymaps["Shift+ArrowUp"],
          "g g": keymaps["Mod+ArrowUp"],
          "shift+g": keymaps["Mod+ArrowDown"],
          "d d": () => shortcuts["cell.delete"](),
          "y y": () => {
            copyCells(selectedCells.size >= 2 ? [...selectedCells] : [cellId]);
            return true;
          },
          p: () => {
            pasteAtCell(cellId, { before: false });
            return true;
          },
          "shift+p": () => {
            pasteAtCell(cellId, { before: true });
            return true;
          },
          o: () => {
            actions.createNewCell({ cellId, before: false, autoFocus: true });
            return true;
          },
          "shift+o": () => {
            actions.createNewCell({ cellId, before: true, autoFocus: true });
            return true;
          },
          u: () => {
            actions.undoDeleteCell();
            return true;
          },
        })
      ) {
        evt.preventDefault();
        return;
      }

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
