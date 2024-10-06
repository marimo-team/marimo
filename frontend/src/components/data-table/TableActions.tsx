/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Tooltip } from "../ui/tooltip";
import { Button } from "../ui/button";
import { PaletteIcon, SearchIcon, Settings } from "lucide-react";
import { DataTablePagination } from "./pagination";
import { DownloadAs, type DownloadActionProps } from "./download-actions";
import type { Table, RowSelectionState } from "@tanstack/react-table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../ui/dropdown-menu";

interface TableActionsProps<TData> {
  enableSearch: boolean;
  onSearchQueryChange?: (query: string) => void;
  isSearchEnabled: boolean;
  setIsSearchEnabled: React.Dispatch<React.SetStateAction<boolean>>;
  pagination: boolean;
  selection?: "single" | "multi" | null;
  onRowSelectionChange?: (value: RowSelectionState) => void;
  table: Table<TData>;
  downloadAs?: DownloadActionProps["downloadAs"];
}

export const TableActions = <TData,>({
  enableSearch,
  onSearchQueryChange,
  isSearchEnabled,
  setIsSearchEnabled,
  pagination,
  selection,
  onRowSelectionChange,
  table,
  downloadAs,
}: TableActionsProps<TData>) => {
  return (
    <div className="flex items-center justify-between flex-shrink-0 pt-1">
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
      {pagination && (
        <DataTablePagination
          selection={selection}
          onSelectAllRowsChange={
            onRowSelectionChange
              ? (value: boolean) => {
                  if (value) {
                    const allKeys = Array.from(
                      { length: table.getRowModel().rows.length },
                      (_, i) => [i, true] as const,
                    );
                    onRowSelectionChange(Object.fromEntries(allKeys));
                  } else {
                    onRowSelectionChange({});
                  }
                }
              : undefined
          }
          table={table}
        />
      )}
      <div className="flex items-center">
        {downloadAs && <DownloadAs downloadAs={downloadAs} />}
        {table.toggleGlobalHeatmap && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild={true}>
              <Button variant="text" size="xs" className="mb-0">
                <Settings className="w-4 h-4 text-muted-foreground" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => table.toggleGlobalHeatmap?.()}>
                <PaletteIcon className="mr-2 h-3.5 w-3.5 text-muted-foreground/70" />
                {table.getGlobalHeatmap?.() ? "Disable" : "Enable"} heatmap
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  );
};
