/* Copyright 2026 Marimo. All rights reserved. */

import type { Cell } from "@tanstack/react-table";
import { useAtomValue } from "jotai";
import { CopyIcon, FilterIcon, SquareStack } from "lucide-react";
import type { RefObject } from "react";
import useEvent from "react-use-event-hook";
import type { DataType } from "@/core/kernel/messages";
import { copyToClipboard } from "@/utils/copy";
import { parseLocalISODate, parseTimeToDate } from "@/utils/dates";
import { Logger } from "@/utils/Logger";
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
import { COMPARISON_OPS, TEXT_SCALAR_OPS } from "./filters/operators";
import { selectedCellsAtom } from "./range-focus/atoms";
import { detectSentinel, getClipboardContent, getRawValue } from "./utils";

const NULLISH_SENTINEL_TYPES = new Set(["null", "nat", "nan"]);

type Comparison = "eq" | "neq";

const symbolOp = {
  eq: COMPARISON_OPS[0],
  neq: COMPARISON_OPS[1],
} as const;

const textOp = {
  eq: TEXT_SCALAR_OPS[1],
  neq: TEXT_SCALAR_OPS[2],
} as const;

export function getContextMenuFilter({
  type,
  value,
  comparison = "eq",
  dataType,
  dtype,
}: {
  type: FilterType | undefined;
  value: unknown;
  comparison?: Comparison;
  dataType?: DataType;
  dtype?: string;
}) {
  const sentinel = detectSentinel(value, dataType, dtype);
  if (sentinel && NULLISH_SENTINEL_TYPES.has(sentinel.type)) {
    return {
      type,
      operator: comparison === "eq" ? "is_null" : "is_not_null",
    };
  }

  switch (type) {
    case "number":
      return Filter.number({
        operator: symbolOp[comparison],
        value: value as number,
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
      const date = new Date(value as string);
      if (Number.isNaN(date.getTime())) {
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
      return undefined;
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
  const handleContextMenuChange = useEvent((open: boolean) => {
    const cell = contextMenuRef.current;
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
  const canFilter = filterType && column.getCanFilter();

  const handleFilterCell = (comparison: Comparison) => {
    const filter = getContextMenuFilter({
      type: filterType,
      value: rawValue,
      comparison,
      dataType,
      dtype,
    });
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
      {canFilter && (
        <>
          <ContextMenuSeparator />
          <ContextMenuItem onClick={() => handleFilterCell("eq")}>
            <FilterIcon className="mo-dropdown-icon h-3 w-3" />
            Filter by this value
          </ContextMenuItem>
          <ContextMenuItem onClick={() => handleFilterCell("neq")}>
            <FilterIcon className="mo-dropdown-icon h-3 w-3" />
            Remove rows with this value
          </ContextMenuItem>
        </>
      )}
    </ContextMenuContent>
  );
};
