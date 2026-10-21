/* Copyright 2026 Marimo. All rights reserved. */

import type { DataType } from "@/core/kernel/messages";
import { assertNever } from "@/utils/assertNever";
import { copyToClipboard } from "@/utils/copy";
import {
  parseLocalISODate,
  parseLocalISODateTime,
  parseTimeToDate,
} from "@/utils/dates";
import { Logger } from "@/utils/Logger";
import type { Cell } from "@tanstack/react-table";
import { useAtomValue } from "jotai";
import { CopyIcon, FilterIcon, SquareStack } from "lucide-react";
import { type RefObject, useRef, useState } from "react";
import useEvent from "react-use-event-hook";
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuPortal,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "../ui/context-menu";
import { DATA_CELL_ID } from "./cell-utils";
import { type FilterType, Filter } from "./filters";
import { selectedCellsAtom } from "./range-focus/atoms";
import { getClipboardContent, getRawValue, isNullishSentinel } from "./utils";

type Comparison = "eq" | "neq";

const symbolOp = {
  eq: "==",
  neq: "!=",
} as const;

const textOp = {
  eq: "equals",
  neq: "does_not_equal",
} as const;

export function buildCellFilter({
  type,
  value,
  comparison = "eq",
  dataType,
  dtype,
}: {
  type: FilterType;
  value: unknown;
  comparison?: Comparison;
  dataType?: DataType;
  dtype?: string;
}) {
  if (isNullishSentinel(value, dataType, dtype)) {
    return { type, operator: comparison === "eq" ? "is_null" : "is_not_null" };
  }

  switch (type) {
    case "number":
      if (typeof value !== "number") {
        return undefined;
      }

      return Filter.number({
        operator: symbolOp[comparison],
        value,
      });
    case "text":
      return Filter.text({
        operator: textOp[comparison],
        text: value as string,
      });
    case "date": {
      const date = parseLocalISODate(value as string);
      if (!date) {
        return undefined;
      }
      return Filter.date({
        operator: symbolOp[comparison],
        value: date,
      });
    }
    case "datetime": {
      const date = parseLocalISODateTime(value as string);
      if (!date) {
        return undefined;
      }
      return Filter.datetime({
        operator: symbolOp[comparison],
        value: date,
      });
    }
    case "time": {
      const time = parseTimeToDate(value as string);
      if (!time) {
        return undefined;
      }
      return Filter.time({
        operator: symbolOp[comparison],
        value: time,
      });
    }
    case "boolean": {
      const target = comparison === "eq" ? value : !(value as boolean);
      return Filter.boolean({
        operator: target ? "is_true" : "is_false",
      });
    }
    default:
      assertNever(type);
  }
}

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
  const [activeCell, setActiveCell] = useState<Cell<TData, unknown> | null>(
    null,
  );
  const highlightedCell = useRef<Element | null>(null);
  const handleContextMenuChange = useEvent((open: boolean) => {
    highlightedCell.current?.classList.remove("bg-(--green-4)");
    highlightedCell.current = null;
    if (!open) {
      return;
    }

    const cell = contextMenuRef.current;
    setActiveCell(cell);
    if (!cell) {
      return;
    }

    // Add a background color to the cell when the context menu is open
    const cellElement = tableRef.current?.querySelector(
      `[${DATA_CELL_ID}="${cell.id}"]`,
    );
    if (!cellElement) {
      Logger.error("Context menu cell not found in table");
      return;
    }

    cellElement.classList.add("bg-(--green-4)");
    highlightedCell.current = cellElement;
  });

  return (
    <ContextMenu onOpenChange={handleContextMenuChange}>
      <ContextMenuTrigger
        asChild={true}
        onContextMenu={() => handleContextMenuChange(true)}
      >
        {tableBody}
      </ContextMenuTrigger>
      <ContextMenuPortal>
        {activeCell && (
          <CellContextMenu cell={activeCell} copySelectedCells={copyAllCells} />
        )}
      </ContextMenuPortal>
    </ContextMenu>
  );
};

export const CellContextMenu = <TData,>({
  cell,
  copySelectedCells,
}: {
  cell: Cell<TData, unknown>;
  copySelectedCells: () => void;
}) => {
  const selectedCells = useAtomValue(selectedCellsAtom);
  const multipleSelectedCells = selectedCells.size > 1;

  const table = cell.getContext().table;
  const displayedValue = cell.getValue();
  const rawValue =
    getRawValue(table, cell.row.index, cell.column.id) ?? displayedValue;

  const handleCopyCell = () => {
    try {
      const { text, html } = getClipboardContent(rawValue, displayedValue);
      copyToClipboard(text, html);
    } catch (error) {
      Logger.error("Failed to copy context menu cell", error);
    }
  };

  const column = cell.column;
  const filterType = column.columnDef.meta?.filterType;
  const dataType = column.columnDef.meta?.dataType;
  const dtype = column.columnDef.meta?.dtype;

  const canFilter = Boolean(filterType && column.getCanFilter());
  const buildFilter = (comparison: Comparison) =>
    canFilter
      ? buildCellFilter({
          type: filterType as FilterType,
          value: rawValue,
          comparison,
          dataType,
          dtype,
        })
      : undefined;
  const eqFilter = buildFilter("eq");
  const canFilterByValue = eqFilter !== undefined;

  const handleFilterCellByValue = (comparison: Comparison) => {
    if (!filterType) {
      return;
    }

    const filter = comparison === "eq" ? eqFilter : buildFilter("neq");

    if (!filter) {
      return;
    }

    column.setFilterValue(filter);
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
      {canFilterByValue && (
        <>
          <ContextMenuSeparator />
          <ContextMenuItem onClick={() => handleFilterCellByValue("eq")}>
            <FilterIcon className="mo-dropdown-icon h-3 w-3" />
            Filter by this value
          </ContextMenuItem>
          <ContextMenuItem onClick={() => handleFilterCellByValue("neq")}>
            <FilterIcon className="mo-dropdown-icon h-3 w-3" />
            Remove rows with this value
          </ContextMenuItem>
        </>
      )}
    </ContextMenuContent>
  );
};
