/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { RowSelectionState, Table } from "@tanstack/react-table";
import {
  ChartBarIcon,
  ChartColumnStacked,
  PanelRightIcon,
  SearchIcon,
} from "lucide-react";
import React from "react";
import type { GetRowIds } from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import type { PanelType } from "../editor/chrome/panels/context-aware-panel/context-aware-panel";
import { Button } from "../ui/button";
import { Tooltip } from "../ui/tooltip";
import { toast } from "../ui/use-toast";
import { type DownloadActionProps, DownloadAs } from "./download-actions";
import { DataTablePagination } from "./pagination";
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
  chartsFeatureEnabled?: boolean;
  togglePanel?: (panelType: PanelType) => void;
  isPanelOpen?: (panelType: PanelType) => boolean;
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
  chartsFeatureEnabled,
  togglePanel,
  isPanelOpen,
}: TableActionsProps<TData>) => {
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
    <div className="flex items-center flex-shrink-0 pt-1">
      {onSearchQueryChange && enableSearch && (
        <Tooltip content="Search">
          <Button
            variant="text"
            size="xs"
            className="mb-0"
            onClick={() => setIsSearchEnabled(!isSearchEnabled)}
          >
            <SearchIcon className="w-4 h-4 text-muted-foreground" />
          </Button>
        </Tooltip>
      )}
      {chartsFeatureEnabled && (
        <Tooltip content="Show charts">
          <Button
            variant="text"
            size="xs"
            className="mb-0"
            onClick={toggleDisplayHeader}
          >
            <ChartBarIcon className="w-4 h-4 text-muted-foreground" />
          </Button>
        </Tooltip>
      )}
      {togglePanel && isPanelOpen !== undefined && (
        <>
          <Tooltip content="Toggle row viewer">
            <Button
              variant="text"
              size="xs"
              onClick={() => togglePanel("row-viewer")}
            >
              <PanelRightIcon
                className={cn(
                  "w-4 h-4 text-muted-foreground",
                  isPanelOpen("row-viewer") && "text-primary",
                )}
              />
            </Button>
          </Tooltip>
          <Tooltip content="Toggle column explorer">
            <Button
              variant="text"
              size="xs"
              onClick={() => togglePanel("column-explorer")}
            >
              <ChartColumnStacked
                className={cn(
                  "w-4 h-4 text-muted-foreground",
                  isPanelOpen("column-explorer") && "text-primary",
                )}
              />
            </Button>
          </Tooltip>
        </>
      )}

      {pagination && (
        <DataTablePagination
          totalColumns={totalColumns}
          selection={selection}
          onSelectAllRowsChange={handleSelectAllRows}
          table={table}
        />
      )}
      <div className="ml-auto">
        {downloadAs && <DownloadAs downloadAs={downloadAs} />}
      </div>
    </div>
  );
};
