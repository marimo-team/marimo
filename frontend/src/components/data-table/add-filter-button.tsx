/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column, Table } from "@tanstack/react-table";
import { PlusIcon } from "lucide-react";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { Button } from "../ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import {
  buildEditorSnapshot,
  editableColumns,
  FilterPillEditor,
  type Snapshot,
} from "./filter-pill-editor";

interface AddFilterButtonProps<TData> {
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
  snapshot: Snapshot | null;
  onSnapshotChange: (snapshot: Snapshot | null) => void;
}

export const AddFilterButton = <TData,>({
  table,
  calculateTopKRows,
  snapshot,
  onSnapshotChange,
}: AddFilterButtonProps<TData>) => {
  const columns = editableColumns(table);

  if (columns.length === 0) {
    return null;
  }

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      onSnapshotChange(null);
      return;
    }
    if (snapshot === null) {
      onSnapshotChange(
        buildEditorSnapshot(columns[0] as Column<unknown, unknown>),
      );
    }
  };

  return (
    <Popover
      open={snapshot !== null}
      onOpenChange={handleOpenChange}
      modal={false}
    >
      <PopoverTrigger asChild={true}>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-5 w-5 -mr-1 rounded-full text-muted-foreground hover:text-foreground"
          aria-label="Add filter"
        >
          <PlusIcon className="h-3.5 w-3.5" aria-hidden={true} />
        </Button>
      </PopoverTrigger>
      {snapshot !== null && (
        <PopoverContent
          className="w-auto p-0"
          align="start"
          alignOffset={-10}
          sideOffset={10}
          avoidCollisions={true}
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <FilterPillEditor
            snapshot={snapshot}
            table={table}
            calculateTopKRows={calculateTopKRows}
            onClose={() => onSnapshotChange(null)}
          />
        </PopoverContent>
      )}
    </Popover>
  );
};
