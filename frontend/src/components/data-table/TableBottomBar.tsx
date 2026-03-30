/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { RowSelectionState, Table } from "@tanstack/react-table";
import React from "react";
import { useLocale } from "react-aria";
import type { GetRowIds } from "@/plugins/impl/DataTablePlugin";
import { toast } from "../ui/use-toast";
import { DataTablePagination, prettifyRowColumnCount } from "./pagination";
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

  return (
    <div className="flex items-center shrink-0 pt-1">
      {pagination ? (
        <DataTablePagination
          totalColumns={totalColumns}
          selection={selection}
          onSelectAllRowsChange={handleSelectAllRows}
          table={table}
          tableLoading={tableLoading}
          showPageSizeSelector={showPageSizeSelector}
        />
      ) : (
        <span className="text-xs text-muted-foreground px-2">
          {prettifyRowColumnCount(table.getRowCount(), totalColumns, locale)}
        </span>
      )}
    </div>
  );
};
