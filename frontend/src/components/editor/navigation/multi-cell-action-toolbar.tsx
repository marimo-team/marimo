/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import { useAtomValue } from "jotai";
import {
  ChevronDownIcon,
  ChevronsDownIcon,
  ChevronsUpIcon,
  ChevronUpIcon,
  Code2Icon,
  EyeIcon,
  EyeOffIcon,
  MoreHorizontalIcon,
  PlayIcon,
  Trash2Icon,
  XCircleIcon,
  ZapIcon,
  ZapOffIcon,
} from "lucide-react";
import React from "react";
import useEvent from "react-use-event-hook";
import { MinimalShortcut } from "@/components/shortcuts/renderShortcut";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  getCellEditorView,
  hasOnlyOneCellAtom,
  notebookAtom,
  useCellActions,
} from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { formatEditorViews } from "@/core/codemirror/format";
import type { HotkeyAction } from "@/core/hotkeys/hotkeys";
import { saveCellConfig } from "@/core/network/requests";
import type { CellConfig } from "@/core/network/types";
import { store } from "@/core/state/jotai";
import { useEventListener } from "@/hooks/useEventListener";
import type { ActionButton } from "../actions/types";
import { useDeleteManyCellsCallback } from "../cell/useDeleteCell";
import { useRunCells } from "../cell/useRunCells";
import { useCellSelectionActions, useCellSelectionState } from "./selection";

interface MultiCellActionButton extends Omit<ActionButton, "handle"> {
  handle: (selectedCells: CellId[]) => void;
  hotkey?: HotkeyAction;
}

const CellStateDropdown: React.FC<{
  actions: MultiCellActionButton[][];
  cellIds: CellId[];
}> = ({ actions, cellIds }) => {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild={true}>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 px-2 gap-1"
          title="More actions"
        >
          <MoreHorizontalIcon size={13} strokeWidth={1.5} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" data-keep-cell-selection={true}>
        {actions.flatMap((group, index) => {
          const groupItems = group.map((action) => {
            return (
              <DropdownMenuItem
                key={action.label}
                onSelect={() => action.handle(cellIds)}
                className="flex items-center gap-2"
              >
                <div className="flex items-center flex-1">
                  {action.icon && (
                    <div className="mr-2 w-5 text-muted-foreground">
                      {action.icon}
                    </div>
                  )}
                  <div className="flex-1">{action.label}</div>
                  {action.hotkey && (
                    <MinimalShortcut
                      shortcut={action.hotkey}
                      className="ml-4"
                    />
                  )}
                </div>
              </DropdownMenuItem>
            );
          });
          return (
            <React.Fragment key={index}>
              {groupItems}
              {index < actions.length - 1 && <DropdownMenuSeparator />}
            </React.Fragment>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export function useMultiCellActionButtons(cellIds: CellId[]) {
  const {
    updateCellConfig,
    moveCell,
    clearCellOutput,
    sendToTop,
    sendToBottom,
  } = useCellActions();
  const deleteCell = useDeleteManyCellsCallback();
  const hasOnlyOneCell = useAtomValue(hasOnlyOneCellAtom);
  const selectionActions = useCellSelectionActions();
  const runCells = useRunCells();

  const selectedCount = cellIds.length;

  const canDelete = !hasOnlyOneCell || selectedCount < cellIds.length;

  const deleteSelectedCells = useEvent((cellIds: CellId[]) => {
    deleteCell({ cellIds });
    selectionActions.clear();
  });

  const moveSelectedCells = useEvent(
    (cellIds: CellId[], direction: "up" | "down") => {
      /// If moving down, make sure the last cell is not at the bottom of the notebook
      if (direction === "down") {
        const lastCellId = cellIds[cellIds.length - 1];
        const notebook = store.get(notebookAtom);
        const isLast =
          notebook.cellIds.findWithId(lastCellId).last() === lastCellId;
        if (isLast) {
          return;
        }
      }

      // If moving up, make sure the first cell is not at the top of the notebook
      if (direction === "up") {
        const firstCellId = cellIds[0];
        const notebook = store.get(notebookAtom);
        const isFirst =
          notebook.cellIds.findWithId(firstCellId).first() === firstCellId;
        if (isFirst) {
          return;
        }
      }

      // Move cells in the appropriate order to maintain relative positions
      const sortedCells = direction === "up" ? cellIds : [...cellIds].reverse();
      sortedCells.forEach((cellId) => {
        moveCell({ cellId, before: direction === "up" });
      });
    },
  );

  const sendSelectedCellsToTop = useEvent((cellIds: CellId[]) => {
    // Send in reverse order to maintain relative positions
    [...cellIds].reverse().forEach((cellId) => {
      sendToTop({ cellId });
    });
  });

  const sendSelectedCellsToBottom = useEvent((cellIds: CellId[]) => {
    cellIds.forEach((cellId) => {
      sendToBottom({ cellId });
    });
  });

  const formatSelectedCells = useEvent((cellIds: CellId[]) => {
    const editorViews: Record<CellId, EditorView> = {};
    cellIds.forEach((cellId) => {
      const editorView = getCellEditorView(cellId);
      if (editorView) {
        editorViews[cellId] = editorView;
      }
    });
    formatEditorViews(editorViews);
  });

  const clearSelectedCellsOutput = useEvent((cellIds: CellId[]) => {
    cellIds.forEach((cellId) => {
      clearCellOutput({ cellId });
    });
  });

  const toggleSelectedCellsProperty = useEvent(
    async (cellIds: CellId[], property: keyof CellConfig, value: boolean) => {
      const configs: Record<CellId, Partial<CellConfig>> = {};
      cellIds.forEach((cellId) => {
        configs[cellId] = { [property]: value };
      });

      await saveCellConfig({ configs });

      cellIds.forEach((cellId) => {
        updateCellConfig({ cellId, config: configs[cellId] });
      });
    },
  );

  const actions: MultiCellActionButton[][] = [
    [
      {
        icon: <PlayIcon size={13} strokeWidth={1.5} />,
        label: "Run cells",
        handle: (cellIds) => runCells(cellIds),
        hotkey: "cell.run",
      },
    ],
    [
      {
        icon: <ChevronUpIcon size={13} strokeWidth={1.5} />,
        label: "Move up",
        handle: (cellIds) => moveSelectedCells(cellIds, "up"),
        hotkey: "cell.moveUp",
      },
      {
        icon: <ChevronDownIcon size={13} strokeWidth={1.5} />,
        label: "Move down",
        handle: (cellIds) => moveSelectedCells(cellIds, "down"),
        hotkey: "cell.moveDown",
      },
    ],
    [
      {
        icon: <Trash2Icon size={13} strokeWidth={1.5} />,
        label: "Delete cells",
        variant: "danger",
        hidden: !canDelete,
        handle: deleteSelectedCells,
      },
    ],
  ];

  const moreActions: MultiCellActionButton[][] = [
    [
      {
        icon: <Code2Icon size={13} strokeWidth={1.5} />,
        label: "Format cells",
        handle: formatSelectedCells,
        hotkey: "cell.format",
      },
      {
        icon: <XCircleIcon size={13} strokeWidth={1.5} />,
        label: "Clear outputs",
        handle: clearSelectedCellsOutput,
      },
    ],
    [
      {
        icon: <EyeOffIcon size={13} strokeWidth={1.5} />,
        label: "Hide code",
        handle: (cellIds) =>
          toggleSelectedCellsProperty(cellIds, "hide_code", true),
        hotkey: "cell.hideCode",
      },
      {
        icon: <EyeIcon size={13} strokeWidth={1.5} />,
        label: "Show code",
        handle: (cellIds) =>
          toggleSelectedCellsProperty(cellIds, "hide_code", false),
        hotkey: "cell.hideCode",
      },
    ],
    [
      {
        icon: <ChevronUpIcon size={13} strokeWidth={1.5} />,
        label: "Move up",
        handle: (cellIds) => moveSelectedCells(cellIds, "up"),
        hotkey: "cell.moveUp",
      },
      {
        icon: <ChevronDownIcon size={13} strokeWidth={1.5} />,
        label: "Move down",
        handle: (cellIds) => moveSelectedCells(cellIds, "down"),
        hotkey: "cell.moveDown",
      },
      {
        icon: <ChevronsUpIcon size={13} strokeWidth={1.5} />,
        label: "Send to top",
        handle: sendSelectedCellsToTop,
        hotkey: "cell.sendToTop",
      },
      {
        icon: <ChevronsDownIcon size={13} strokeWidth={1.5} />,
        label: "Send to bottom",
        handle: sendSelectedCellsToBottom,
        hotkey: "cell.sendToBottom",
      },
    ],
    [
      {
        icon: <ZapOffIcon size={13} strokeWidth={1.5} />,
        label: "Disable cells",
        handle: (cellIds) =>
          toggleSelectedCellsProperty(cellIds, "disabled", true),
      },
      {
        icon: <ZapIcon size={13} strokeWidth={1.5} />,
        label: "Enable cells",
        handle: (cellIds) =>
          toggleSelectedCellsProperty(cellIds, "disabled", false),
      },
    ],
  ];

  // Filter out hidden actions and empty groups
  return {
    actions: actions
      .map((group) => group.filter((action) => !action.hidden))
      .filter((group) => group.length > 0),
    moreActions: moreActions
      .map((group) => group.filter((action) => !action.hidden))
      .filter((group) => group.length > 0),
  };
}

export const MultiCellActionToolbar = () => {
  const selectionState = useCellSelectionState();
  const selectedCells = [...selectionState.selected];

  if (selectedCells.length < 2) {
    return null;
  }

  return <MultiCellActionToolbarInternal cellIds={selectedCells} />;
};

const Separator = () => <div className="h-4 w-px bg-border mx-1" />;

const MultiCellActionToolbarInternal = ({ cellIds }: { cellIds: CellId[] }) => {
  const selectionActions = useCellSelectionActions();
  const { actions, moreActions } = useMultiCellActionButtons(cellIds);

  const selectedCount = cellIds.length;

  useEventListener(window, "mousedown", (evt) => {
    // Clear selected, unless clicked inside an element that contains data-keep-cell-selection
    if (
      (evt.target instanceof HTMLElement || evt.target instanceof SVGElement) &&
      evt.target.closest("[data-keep-cell-selection]") !== null
    ) {
      return;
    }

    // HACK: evt.target is the root <html> element
    // when the DropdownMenu is closed.
    // This prevents the selection from being cleared when the opens/closes
    // the DropdownMenu.
    if (evt.target instanceof HTMLHtmlElement) {
      return;
    }
    selectionActions.clear();
  });

  return (
    <div
      className="absolute top-12 justify-center flex w-full left-0 right-0 z-50"
      data-keep-cell-selection={true}
    >
      <div className="bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border border-[var(--slate-7)] rounded-lg shadow-lg p-2 overflow-x-auto overflow-y-hidden mx-20 scrollbar-thin">
        <div className="flex items-center gap-1">
          <span className="text-sm font-medium text-muted-foreground px-2 flex-shrink-0">
            {selectedCount} cells selected
          </span>
          <Separator />
          {actions.map((group, groupIndex) => (
            <div
              key={groupIndex}
              className="flex items-center gap-2 flex-shrink-0"
            >
              {group.map((action) => (
                <Button
                  key={action.label}
                  variant={
                    action.variant === "danger" ? "linkDestructive" : "ghost"
                  }
                  size="sm"
                  onClick={() => action.handle(cellIds)}
                  className="h-8 px-2 gap-1 flex-shrink-0 flex items-center"
                  title={action.label}
                >
                  {action.icon}
                  <span className="text-xs">{action.label}</span>
                  {action.hotkey && (
                    <div className="ml-1 border bg-muted rounded-md px-1">
                      <MinimalShortcut shortcut={action.hotkey} />
                    </div>
                  )}
                </Button>
              ))}
              {groupIndex < actions.length - 1 && <Separator />}
            </div>
          ))}
          <Separator />
          <CellStateDropdown actions={moreActions} cellIds={cellIds} />
        </div>
      </div>
    </div>
  );
};
