/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { RowSelectionState, Table } from "@tanstack/react-table";
import { ChartSplineIcon, PanelRightIcon, SearchIcon } from "lucide-react";
import React from "react";
import { useLocale } from "react-aria";
import type { GetRowIds } from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import {
  PANEL_TYPES,
  type PanelType,
} from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { Button } from "../ui/button";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";
import { type DownloadActionProps, DownloadAs } from "./download-actions";
import { DataTablePagination, prettifyRowColumnCount } from "./pagination";
import type { DataTableSelection } from "./types";

interface TableActionsProps<TData> {
  enableSearch: boolean;
  onSearchQueryChange?: (query: string) => void;
  isSearchEnabled: boolean;
  setIsSearchEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  pagination: boolean;
  totalColumns: number;
  selection?: DataTableSelection;
  onRowSelectionChange?: (value: RowSelectionState) => void;
  table: Table<TData>;
  downloadAs?: DownloadActionProps["downloadAs"];
  getRowIds?: GetRowIds;
  toggleDisplayHeader?: () => void;
  showChartBuilder?: boolean;
  showTableExplorer?: boolean;
  showPageSizeSelector?: boolean;
  togglePanel?: (panelType: PanelType) => void;
  isAnyPanelOpen?: boolean;
  tableLoading?: boolean;
}

export const TableActions = <TData,>({
  enableSearch,
  onSearchQueryChange,
  isSearchEnabled,
  setIsSearchEnabled,
  pagination,
  totalColumns,
  selection,
  onRowSelectionChange,
  table,
  downloadAs,
  getRowIds,
  toggleDisplayHeader,
  showChartBuilder,
  showTableExplorer,
  showPageSizeSelector,
  togglePanel,
  isAnyPanelOpen,
  tableLoading,
}: TableActionsProps<TData>) => {
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
      {onSearchQueryChange && enableSearch && (
        <Tooltip content="Search">
          <Button
            variant="text"
            size="xs"
            className="mb-0 print:hidden"
            onClick={() => setIsSearchEnabled(!isSearchEnabled)}
          >
            <SearchIcon className="w-4 h-4 text-muted-foreground" />
          </Button>
        </Tooltip>
      )}
      {showChartBuilder && (
        <Tooltip content="Chart builder">
          <Button
            variant="text"
            size="xs"
            className="mb-0 print:hidden"
            onClick={toggleDisplayHeader}
          >
            <ChartSplineIcon className="w-4 h-4 text-muted-foreground" />
          </Button>
        </Tooltip>
      )}
      {showTableExplorer && togglePanel && (
        <Tooltip content="Toggle table explorer">
          <Button
            variant="text"
            size="xs"
            onClick={() => togglePanel(PANEL_TYPES.ROW_VIEWER)}
            className="print:hidden"
          >
            <PanelRightIcon
              className={cn(
                "w-4 h-4 text-muted-foreground",
                isAnyPanelOpen && "text-primary",
              )}
            />
          </Button>
        </Tooltip>
      )}

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
      <div className="ml-auto">
        {downloadAs && <DownloadAs downloadAs={downloadAs} />}
      </div>
    </div>
  );
};
