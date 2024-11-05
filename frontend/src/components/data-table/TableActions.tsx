/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import React from "react";
import { Tooltip } from "../ui/tooltip";
import { Button } from "../ui/button";
import { SearchIcon } from "lucide-react";
import { DataTablePagination } from "./pagination";
import { DownloadAs, type DownloadActionProps } from "./download-actions";
import type { Table, RowSelectionState } from "@tanstack/react-table";

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
      {pagination ? (
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
      ) : (
        <div />
      )}
      {downloadAs && <DownloadAs downloadAs={downloadAs} />}
    </div>
  );
};
