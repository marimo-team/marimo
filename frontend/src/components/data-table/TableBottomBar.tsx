/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { RowSelectionState, Table } from "@tanstack/react-table";
import { useLocale } from "react-aria";
import type { GetRowIds } from "@/plugins/impl/DataTablePlugin";
import { Events } from "@/utils/events";
import { prettyNumber } from "@/utils/numbers";
import { Button } from "../ui/button";
import { toast } from "../ui/use-toast";
import { DataTablePagination, prettifyRowColumnCount } from "./pagination";
import { CellSelectionStats } from "./range-focus/cell-selection-stats";
import type { DataTableSelection } from "./types";

interface TableBottomBarProps<TData> {
  pagination: boolean;
  totalColumns: number;
  selection?: DataTableSelection;
  onRowSelectionChange?: (value: RowSelectionState) => void;
  table: Table<TData>;
  getRowIds?: GetRowIds;
  showPageSizeSelector?: boolean;
  tableLoading?: boolean;
}

export const TableBottomBar = <TData,>({
  pagination,
  totalColumns,
  selection,
  onRowSelectionChange,
  table,
  getRowIds,
  showPageSizeSelector,
  tableLoading,
}: TableBottomBarProps<TData>) => {
  const { locale } = useLocale();
  const handleSelectAllRows = (value: boolean) => {
    if (!onRowSelectionChange) {
      return;
    }

    // Clear all selections
    if (!value) {
      onRowSelectionChange({});
      return;
    }

    const selectAllRowsByIndex = () => {
      const allKeys = Array.from(
        { length: table.getRowCount() },
        (_, i) => [i, true] as const,
      );
      onRowSelectionChange(Object.fromEntries(allKeys));
    };

    if (!getRowIds) {
      selectAllRowsByIndex();
      return;
    }

    getRowIds({}).then((data) => {
      if (data.error) {
        toast({
          title: "Not available",
          description: data.error,
          variant: "danger",
        });
        return;
      }

      if (data.all_rows) {
        selectAllRowsByIndex();
      } else {
        onRowSelectionChange(
          Object.fromEntries(data.row_ids.map((id) => [id, true])),
        );
      }
    });
  };

  const renderTotal = () => {
    const { rowSelection, cellSelection } = table.getState();
    let selected = Object.keys(rowSelection).length;
    let isAllPageSelected = table.getIsAllPageRowsSelected();
    const numRows = table.getRowCount();
    let isAllSelected = selected === numRows;

    const isCellSelection =
      selection === "single-cell" || selection === "multi-cell";
    if (isCellSelection) {
      selected = cellSelection.length;
      isAllPageSelected = false;
      isAllSelected = false;
    }

    if (isAllPageSelected && !isAllSelected) {
      return (
        <>
          <span>{prettyNumber(selected, locale)} selected</span>
          <Button
            size="xs"
            data-testid="select-all-button"
            variant="link"
            className="h-4 print:hidden"
            onMouseDown={Events.preventFocus}
            onClick={() => handleSelectAllRows(true)}
          >
            Select all {prettyNumber(numRows, locale)}
          </Button>
        </>
      );
    }

    if (selected) {
      return (
        <>
          <span>{prettyNumber(selected, locale)} selected</span>
          <Button
            size="xs"
            data-testid="clear-selection-button"
            variant="link"
            className="h-4 print:hidden"
            onMouseDown={Events.preventFocus}
            onClick={() => {
              if (!isCellSelection) {
                handleSelectAllRows(false);
              } else if (table.resetCellSelection) {
                table.resetCellSelection();
              }
            }}
          >
            Clear selection
          </Button>
        </>
      );
    }

    return (
      <span>
        {prettifyRowColumnCount(table.getRowCount(), totalColumns, locale)}
      </span>
    );
  };

  return (
    <div className="flex lg:grid lg:grid-cols-[1fr_auto_1fr] items-center shrink-0 pt-1">
      <div className="flex flex-col text-sm text-muted-foreground px-2 shrink-0">
        <div className="flex items-center gap-1">{renderTotal()}</div>
        <CellSelectionStats table={table} className="lg:hidden" />
      </div>
      <div className="ml-auto lg:ml-0 lg:justify-self-center flex items-center shrink-0">
        {pagination && (
          <DataTablePagination
            table={table}
            tableLoading={tableLoading}
            showPageSizeSelector={showPageSizeSelector}
          />
        )}
      </div>
      <div className="hidden lg:flex justify-end">
        <CellSelectionStats table={table} className="px-2" />
      </div>
    </div>
  );
};
