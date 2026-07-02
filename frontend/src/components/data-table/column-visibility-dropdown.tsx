/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

// tanstack/table is not compatible with React compiler
// https://github.com/TanStack/table/issues/5567

import type { Table } from "@tanstack/react-table";
import { Columns3Icon, EyeIcon, EyeOffIcon } from "lucide-react";
import React from "react";
import { ColumnName } from "@/components/datasources/components";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { type BulkAction, useSelectList } from "@/components/ui/select-core";
import type { DataType } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { smartMatchFilter } from "@/utils/smartMatch";
import { NAMELESS_COLUMN_PREFIX } from "./columns";
import { INDEX_COLUMN_NAME, SELECT_COLUMN_ID } from "./types";

function getUserColumns<TData>(table: Table<TData>) {
  return table
    .getAllLeafColumns()
    .filter(
      (column) =>
        column.id !== SELECT_COLUMN_ID &&
        column.id !== INDEX_COLUMN_NAME &&
        !column.id.startsWith(NAMELESS_COLUMN_PREFIX),
    );
}

export const ColumnVisibilityDropdown = <TData,>({
  table,
}: {
  table: Table<TData>;
}) => {
  const userColumns = getUserColumns(table);
  const options = userColumns.map((column) => ({
    value: column.id,
    label: column.id,
    disabled: !column.getCanHide(),
    data: { dataType: column.columnDef.meta?.dataType },
  }));
  // Modeled as a select list over hidden columns: "selected" means hidden, so
  // the hook's pinning floats hidden columns to the top and freezes that order
  // while the menu is open.
  const hiddenIds = userColumns
    .filter((column) => !column.getIsVisible())
    .map((column) => column.id);

  const applyHidden = (next: string[] | string | null) => {
    const hidden = new Set(Array.isArray(next) ? next : []);
    table.setColumnVisibility((previous) => ({
      ...previous,
      ...Object.fromEntries(
        userColumns.map((column) => [column.id, !hidden.has(column.id)]),
      ),
    }));
  };

  const list = useSelectList<string>({
    options,
    value: hiddenIds,
    onChange: applyHidden,
    multiple: true,
    filterFn: smartMatchFilter,
    pinSelected: true,
  });
  // With selection modeling hidden columns, select-matching hides the visible
  // matches and deselect-matching shows the hidden ones.
  const matchingActions = list.bulkActions.filter(
    (
      action,
    ): action is Extract<
      BulkAction<string>,
      { kind: "select-matching" | "deselect-matching" }
    > =>
      action.kind === "select-matching" || action.kind === "deselect-matching",
  );

  return (
    <Popover open={list.open} onOpenChange={list.setOpen}>
      <PopoverTrigger asChild={true}>
        <Button
          variant="text"
          size="xs"
          data-testid="column-visibility-trigger"
          onMouseDown={Events.preventFocus}
          className={cn(
            "print:hidden text-xs gap-1",
            list.open ? "text-primary" : "text-muted-foreground",
          )}
        >
          <Columns3Icon className="w-3.5 h-3.5" />
          Columns
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="end">
        <Command shouldFilter={false}>
          <CommandInput
            placeholder="Search columns..."
            value={list.searchQuery}
            onValueChange={list.setSearchQuery}
          />
          <CommandList>
            <CommandEmpty>No results.</CommandEmpty>
            {list.searchQuery === "" ? (
              <>
                <CommandItem
                  value="__show_all__"
                  disabled={hiddenIds.length === 0}
                  onSelect={() => applyHidden([])}
                  className="cursor-pointer"
                >
                  <EyeIcon className="w-3 h-3 mr-1.5" />
                  Show all
                </CommandItem>
                <CommandSeparator />
              </>
            ) : (
              matchingActions.length > 0 && (
                <>
                  {matchingActions.map((action) => (
                    <CommandItem
                      key={action.kind}
                      value={`__bulk_${action.kind}`}
                      onSelect={action.run}
                      className="cursor-pointer"
                    >
                      {action.kind === "select-matching" ? (
                        <EyeOffIcon className="w-3 h-3 mr-1.5" />
                      ) : (
                        <EyeIcon className="w-3 h-3 mr-1.5" />
                      )}
                      {action.kind === "select-matching" ? "Hide" : "Show"}{" "}
                      {action.items.length} matching
                    </CommandItem>
                  ))}
                  <CommandSeparator />
                </>
              )
            )}
            {list.visibleOptions.map((option, index) => {
              const hidden = list.isChecked(option.value);
              const { dataType } = option.data as {
                dataType: DataType | undefined;
              };
              const isSectionBoundary =
                index === list.pinnedCount &&
                list.pinnedCount > 0 &&
                list.pinnedCount < list.visibleOptions.length;
              return (
                <React.Fragment key={option.value}>
                  {isSectionBoundary && <CommandSeparator />}
                  <CommandItem
                    value={option.value}
                    disabled={option.disabled}
                    onSelect={() => list.toggle(option.value)}
                    className="flex items-center gap-1.5 cursor-pointer"
                  >
                    {dataType === undefined ? (
                      <span>{option.label}</span>
                    ) : (
                      <ColumnName
                        columnName={option.label}
                        dataType={dataType}
                      />
                    )}
                    {!option.disabled && (
                      <span
                        className={cn(
                          "ml-auto",
                          hidden ? "text-primary" : "text-muted-foreground",
                        )}
                      >
                        {hidden ? (
                          <EyeOffIcon className="w-3 h-3" />
                        ) : (
                          <EyeIcon className="w-3 h-3" />
                        )}
                      </span>
                    )}
                  </CommandItem>
                </React.Fragment>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
};
