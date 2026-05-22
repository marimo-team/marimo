/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column, Table } from "@tanstack/react-table";
import { EllipsisIcon, FilterIcon, ListFilterIcon } from "lucide-react";
import { useLocale } from "react-aria";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { cn } from "@/utils/cn";
import { useFilterEditor } from "./filter-editor-context";
import { EDITABLE_FILTER_TYPES, isMembershipFilterType } from "./filters";
import {
  ClearFilterMenuItem,
  renderColumnPinning,
  renderColumnWrapping,
  renderCopyColumn,
  renderDataType,
  renderFormatOptions,
  renderSortIcon,
  renderSorts,
} from "./header-items";

interface DataTableColumnHeaderProps<
  TData,
  TValue,
> extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>;
  header: React.ReactNode;
  subheader?: React.ReactNode;
  justify?: "left" | "center" | "right";
  calculateTopKRows?: CalculateTopKRows;
  table?: Table<TData>;
}

export const DataTableColumnHeader = <TData, TValue>({
  column,
  header,
  subheader,
  justify,
  className,
  table,
}: DataTableColumnHeaderProps<TData, TValue>) => {
  const { locale } = useLocale();
  const editor = useFilterEditor();

  // No header
  if (!header) {
    return null;
  }

  // No sorting or filtering
  if (!column.getCanSort() && !column.getCanFilter()) {
    return (
      <div
        className={cn(
          justify === "center" && "text-center",
          justify === "right" && "text-right",
          className,
        )}
      >
        {header}
        {subheader}
      </div>
    );
  }

  const hasFilter = column.getFilterValue() !== undefined;
  const filterType = column.columnDef.meta?.filterType;
  const canEditFilter =
    editor !== null &&
    column.getCanFilter() &&
    filterType !== undefined &&
    EDITABLE_FILTER_TYPES.has(filterType);
  const canFilterByValues =
    canEditFilter &&
    filterType !== undefined &&
    isMembershipFilterType(filterType);

  return (
    <div
      className={cn("group flex flex-col my-1 w-full select-none", className)}
    >
      <div
        className={cn(
          "flex items-center gap-1",
          justify === "right" && "flex-row-reverse",
          justify === "center" && "mx-auto",
        )}
      >
        {justify === "center" ? (
          <>
            {column.getCanSort() && <SortButton column={column} />}
            {hasFilter && <FilterIndicator />}
            <span>{header}</span>
          </>
        ) : (
          <>
            <span>{header}</span>
            {hasFilter && <FilterIndicator />}
            {column.getCanSort() && <SortButton column={column} />}
          </>
        )}
        <DropdownMenu modal={false}>
          <DropdownMenuTrigger asChild={true}>
            <button
              type="button"
              className="inline-flex items-center justify-center h-5 w-5 rounded hover:bg-(--slate-4) text-muted-foreground opacity-0 group-hover:opacity-100 focus:opacity-100 group-focus-within:opacity-100 data-[state=open]:opacity-100 data-[state=open]:text-accent-foreground"
              aria-label="Column options"
              data-testid="data-table-column-menu-button"
            >
              <EllipsisIcon className="h-3.5 w-3.5" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start">
            {renderDataType(column)}
            {renderSorts(column, table)}
            {renderCopyColumn(column)}
            {renderColumnPinning(column)}
            {renderColumnWrapping(column)}
            {renderFormatOptions(column, locale)}
            {canEditFilter && <DropdownMenuSeparator />}
            {canEditFilter && (
              <DropdownMenuItem
                onSelect={() =>
                  editor.requestAddFilter({ columnId: column.id })
                }
              >
                <FilterIcon className="mo-dropdown-icon" />
                Filter
              </DropdownMenuItem>
            )}
            {canFilterByValues && (
              <DropdownMenuItem
                onSelect={() =>
                  editor.requestAddFilter({
                    columnId: column.id,
                    operator: "in",
                  })
                }
              >
                <ListFilterIcon className="mo-dropdown-icon" />
                Filter by values
              </DropdownMenuItem>
            )}
            {hasFilter && <ClearFilterMenuItem column={column} />}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {subheader}
    </div>
  );
};

const FilterIndicator = () => (
  <span
    className="inline-flex items-center justify-center h-5 w-5 text-primary"
    aria-label="Column is filtered"
  >
    <FilterIcon className="h-3 w-3" aria-hidden={true} />
  </span>
);

const SortButton = <TData, TValue>({
  column,
}: {
  column: Column<TData, TValue>;
}) => {
  const sortDirection = column.getIsSorted();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!sortDirection) {
      column.toggleSorting(false, true); // asc
    } else if (sortDirection === "asc") {
      column.toggleSorting(true, true); // desc
    } else {
      column.clearSorting();
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        "inline-flex items-center justify-center h-5 w-5 rounded hover:bg-(--slate-4)",
        sortDirection
          ? "text-accent-foreground"
          : "text-muted-foreground opacity-0 group-hover:opacity-100 focus:opacity-100 group-focus-within:opacity-100",
      )}
      aria-label={
        sortDirection === "asc"
          ? "Sorted ascending, click to sort descending"
          : sortDirection === "desc"
            ? "Sorted descending, click to clear sort"
            : "Sort column ascending"
      }
      data-testid="data-table-sort-button"
    >
      {renderSortIcon(column)}
    </button>
  );
};
