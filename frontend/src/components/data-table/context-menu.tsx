/* Copyright 2024 Marimo. All rights reserved. */

import type { Cell } from "@tanstack/react-table";
import { useAtomValue } from "jotai";
import { CopyIcon, FilterIcon, SquareStack } from "lucide-react";
import type { RefObject } from "react";
import useEvent from "react-use-event-hook";
import { copyToClipboard } from "@/utils/copy";
import { Logger } from "@/utils/Logger";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuPortal,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "../ui/context-menu";
import { Filter } from "./filters";
import { selectedCellsAtom } from "./range-focus/atoms";
import { stringifyUnknownValue } from "./utils";

export const DataTableContextMenu = <TData,>({
  contextMenuRef,
  tableBody,
  tableRef,
  copyAllCells,
}: {
  contextMenuRef: RefObject<Cell<TData, unknown> | null>;
  tableBody: React.ReactNode;
  tableRef: RefObject<HTMLTableSectionElement | null>;
  copyAllCells: () => void;
}) => {
  const handleContextMenuChange = useEvent((open: boolean) => {
    const cell = contextMenuRef.current;
    if (!cell) {
      return;
    }

    // Add a background color to the cell when the context menu is open
    const cellElement = tableRef.current?.querySelector(
      `[data-cell-id="${cell.id}"]`,
    );
    if (!cellElement) {
      Logger.error("Context menu cell not found in table");
      return;
    }

    if (open) {
      cellElement.classList.add("bg-(--green-4)");
    } else {
      cellElement.classList.remove("bg-(--green-4)");
    }
  });

  return (
    <ContextMenu onOpenChange={handleContextMenuChange}>
      <ContextMenuTrigger asChild={true}>{tableBody}</ContextMenuTrigger>
      <ContextMenuPortal>
        <CellContextMenu
          cellRef={contextMenuRef}
          copySelectedCells={copyAllCells}
        />
      </ContextMenuPortal>
    </ContextMenu>
  );
};

export const CellContextMenu = <TData,>({
  cellRef,
  copySelectedCells,
}: {
  cellRef: RefObject<Cell<TData, unknown> | null>;
  copySelectedCells: () => void;
}) => {
  const selectedCells = useAtomValue(selectedCellsAtom);
  const multipleSelectedCells = selectedCells.size > 1;

  const cell = cellRef.current;
  if (!cell) {
    Logger.error("No cell found in context menu");
    return;
  }

  const handleCopyCell = () => {
    try {
      const value = cell.getValue();
      const stringValue = stringifyUnknownValue({ value });
      copyToClipboard(stringValue);
    } catch (error) {
      Logger.error("Failed to copy context menu cell", error);
    }
  };

  const column = cell.column;
  const canFilter = column.getCanFilter() && column.columnDef.meta?.filterType;

  const handleFilterCell = () => {
    column.setFilterValue(
      Filter.select({
        options: [cell.getValue()],
        operator: "in",
      }),
    );
  };

  return (
    <ContextMenuContent>
      <ContextMenuItem onClick={handleCopyCell}>
        <CopyIcon className="mo-dropdown-icon h-3 w-3" />
        Copy cell
      </ContextMenuItem>
      {multipleSelectedCells && (
        <ContextMenuItem onClick={copySelectedCells}>
          <SquareStack className="mo-dropdown-icon h-3 w-3" />
          Copy selected cells
        </ContextMenuItem>
      )}
      {canFilter && (
        <>
          <ContextMenuSeparator />
          <ContextMenuItem onClick={handleFilterCell}>
            <FilterIcon className="mo-dropdown-icon h-3 w-3" />
            Filter by this value
          </ContextMenuItem>
        </>
      )}
    </ContextMenuContent>
  );
};
