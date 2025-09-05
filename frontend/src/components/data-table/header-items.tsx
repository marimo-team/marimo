/* Copyright 2024 Marimo. All rights reserved. */

import { PinLeftIcon, PinRightIcon } from "@radix-ui/react-icons";
import type { Column, Table, SortingState } from "@tanstack/react-table";
import {
  AlignJustifyIcon,
  ArrowDownWideNarrowIcon,
  ArrowUpNarrowWideIcon,
  ChevronsUpDown,
  CopyIcon,
  FilterX,
  FunnelPlusIcon,
  ListFilterIcon,
  ListFilterPlusIcon,
  PinOffIcon,
  WrapTextIcon,
  XIcon,
} from "lucide-react";
import {
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu";
import type { DataType } from "@/core/kernel/messages";
import { cn } from "@/utils/cn";
import { copyToClipboard } from "@/utils/copy";
import { DATA_TYPE_ICON } from "../datasets/icons";
import { Button } from "../ui/button";
import { formattingExample } from "./column-formatting/feature";
import { formatOptions } from "./column-formatting/types";
import { NAMELESS_COLUMN_PREFIX } from "./columns";

export function renderFormatOptions<TData, TValue>(
  column: Column<TData, TValue>,
) {
  const dataType: DataType | undefined = column.columnDef.meta?.dataType;
  const columnFormatOptions = dataType ? formatOptions[dataType] : [];

  if (columnFormatOptions.length === 0 || !column.getCanFormat?.()) {
    return null;
  }
  const FormatIcon = DATA_TYPE_ICON[dataType || "unknown"];
  const currentFormat = column.getColumnFormatting?.();
  return (
    <DropdownMenuSub>
      <DropdownMenuSubTrigger>
        <FormatIcon className="mo-dropdown-icon" />
        Format
      </DropdownMenuSubTrigger>
      <DropdownMenuPortal>
        <DropdownMenuSubContent>
          {Boolean(currentFormat) && (
            <>
              <DropdownMenuItem
                key={"clear"}
                variant={"danger"}
                onClick={() => column.setColumnFormatting(undefined)}
              >
                Clear
              </DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          )}
          {columnFormatOptions.map((option) => (
            <DropdownMenuItem
              key={option}
              onClick={() => column.setColumnFormatting(option)}
            >
              <span className={cn(currentFormat === option && "font-semibold")}>
                {option}
              </span>
              <span className="ml-auto pl-5 text-xs text-muted-foreground">
                {formattingExample(option)}
              </span>
            </DropdownMenuItem>
          ))}
        </DropdownMenuSubContent>
      </DropdownMenuPortal>
    </DropdownMenuSub>
  );
}

export function renderColumnWrapping<TData, TValue>(
  column: Column<TData, TValue>,
) {
  if (!column.getCanWrap?.() || !column.getColumnWrapping) {
    return null;
  }

  const wrap = column.getColumnWrapping();
  if (wrap === "wrap") {
    return (
      <DropdownMenuItem onClick={() => column.toggleColumnWrapping("nowrap")}>
        <AlignJustifyIcon className="mo-dropdown-icon" />
        No wrap text
      </DropdownMenuItem>
    );
  }

  return (
    <DropdownMenuItem onClick={() => column.toggleColumnWrapping("wrap")}>
      <WrapTextIcon className="mo-dropdown-icon" />
      Wrap text
    </DropdownMenuItem>
  );
}

export function renderColumnPinning<TData, TValue>(
  column: Column<TData, TValue>,
) {
  if (!column.getCanPin?.() || !column.getIsPinned) {
    return null;
  }

  const pinnedPosition = column.getIsPinned();

  if (pinnedPosition !== false) {
    return (
      <DropdownMenuItem onClick={() => column.pin(false)}>
        <PinOffIcon className="mo-dropdown-icon" />
        Unfreeze
      </DropdownMenuItem>
    );
  }

  return (
    <>
      <DropdownMenuItem onClick={() => column.pin("left")}>
        <PinLeftIcon className="mo-dropdown-icon" />
        Freeze left
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => column.pin("right")}>
        <PinRightIcon className="mo-dropdown-icon" />
        Freeze right
      </DropdownMenuItem>
    </>
  );
}

export function renderCopyColumn<TData, TValue>(column: Column<TData, TValue>) {
  if (!column.getCanCopy?.()) {
    return null;
  }

  if (column.id.startsWith(NAMELESS_COLUMN_PREFIX)) {
    return null;
  }

  return (
    <DropdownMenuItem onClick={async () => await copyToClipboard(column.id)}>
      <CopyIcon className="mo-dropdown-icon" />
      Copy column name
    </DropdownMenuItem>
  );
}

const AscIcon = ArrowUpNarrowWideIcon;
const DescIcon = ArrowDownWideNarrowIcon;

export function renderSorts<TData, TValue>(column: Column<TData, TValue>, table?: Table<TData>) {
  if (!column.getCanSort()) {
    return null;
  }

  // Try to get table from column (TanStack Table should provide this)
  const tableFromColumn = (column as any).table || table;

  // If table is available (either passed or from column), use full multi-column sort functionality
  if (tableFromColumn) {
    const sortingState: SortingState = tableFromColumn.getState().sorting;
    const currentSort = sortingState.find((s) => s.id === column.id);
    const sortIndex = currentSort ? sortingState.indexOf(currentSort) + 1 : null;

    return (
      <>
        <DropdownMenuItem onClick={() => column.toggleSorting(false, true)}>
          <AscIcon className="mo-dropdown-icon" />
          Sort Ascending
          {sortIndex && currentSort && !currentSort.desc && (
            <span className="ml-auto text-xs bg-blue-100 text-blue-800 px-1 rounded">
              {sortIndex}
            </span>
          )}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => column.toggleSorting(true, true)}>
          <DescIcon className="mo-dropdown-icon" />
          Sort Descending
          {sortIndex && currentSort && currentSort.desc && (
            <span className="ml-auto text-xs bg-blue-100 text-blue-800 px-1 rounded">
              {sortIndex}
            </span>
          )}
        </DropdownMenuItem>
        {currentSort && (
          <DropdownMenuItem onClick={() => column.clearSorting()}>
            <XIcon className="mo-dropdown-icon" />
            Remove Sort
            <span className="ml-auto text-xs bg-red-100 text-red-800 px-1 rounded">
              {sortIndex}
            </span>
          </DropdownMenuItem>
        )}
        {sortingState.length > 0 && (
          <DropdownMenuItem onClick={() => tableFromColumn.resetSorting()}>
            <FilterX className="mo-dropdown-icon" />
            Clear All Sorts
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
      </>
    );
  }

  // Fallback to simple sorting if table not provided
  const isSorted = column.getIsSorted();

  return (
    <>
      <DropdownMenuItem onClick={() => column.toggleSorting(false, true)}>
        <AscIcon className="mo-dropdown-icon" />
        Sort Ascending
        {isSorted === "asc" && (
          <span className="ml-auto text-xs bg-blue-100 text-blue-800 px-1 rounded">
            ✓
          </span>
        )}
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => column.toggleSorting(true, true)}>
        <DescIcon className="mo-dropdown-icon" />
        Sort Descending
        {isSorted === "desc" && (
          <span className="ml-auto text-xs bg-blue-100 text-blue-800 px-1 rounded">
            ✓
          </span>
        )}
      </DropdownMenuItem>
      {isSorted && (
        <DropdownMenuItem onClick={() => column.clearSorting()}>
          <XIcon className="mo-dropdown-icon" />
          Remove Sort
        </DropdownMenuItem>
      )}
      <DropdownMenuSeparator />
    </>
  );
}

export function renderSortFilterIcon<TData, TValue>(
  column: Column<TData, TValue>,
) {
  if (!column.getCanSort()) {
    return null;
  }

  const isSorted = column.getIsSorted();
  const isFiltered = column.getFilterValue() !== undefined;

  let Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  if (isFiltered && isSorted) {
    Icon = ListFilterPlusIcon;
  } else if (isFiltered) {
    Icon = FunnelPlusIcon;
  } else if (isSorted) {
    Icon = isSorted === "desc" ? DescIcon : AscIcon;
  } else {
    Icon = ChevronsUpDown;
  }

  return <Icon className="h-3 w-3" />;
}

export function renderDataType<TData, TValue>(column: Column<TData, TValue>) {
  const dtype: string | undefined = column.columnDef.meta?.dtype;
  if (!dtype) {
    return null;
  }

  return (
    <>
      <div className="flex-1 px-2 text-xs text-muted-foreground font-bold">
        {dtype}
      </div>
      <DropdownMenuSeparator />
    </>
  );
}

export const ClearFilterMenuItem = <TData, TValue>({
  column,
}: {
  column: Column<TData, TValue>;
}) => (
  <DropdownMenuItem onClick={() => column.setFilterValue(undefined)}>
    <FilterX className="mo-dropdown-icon" />
    Clear filter
  </DropdownMenuItem>
);

export function renderFilterByValues<TData, TValue>(
  column: Column<TData, TValue>,
  setIsFilterValueOpen: (open: boolean) => void,
) {
  const canFilter = column.getCanFilter();
  if (!canFilter) {
    return null;
  }

  const columnType = column.columnDef.meta?.dataType;
  // skip boolean as this can be easily filtered through normal filters
  if (columnType === "boolean") {
    return null;
  }

  // there are some edge cases which do not support filtering (eg. dicts with None values)
  const filterType = column.columnDef.meta?.filterType;
  if (!filterType) {
    return null;
  }

  return (
    <DropdownMenuSub>
      <DropdownMenuItem onClick={() => setIsFilterValueOpen(true)}>
        <ListFilterIcon className="mo-dropdown-icon" />
        Filter by values
      </DropdownMenuItem>
    </DropdownMenuSub>
  );
}

export const FilterButtons = ({
  onApply,
  onClear,
  clearButtonDisabled,
}: {
  onApply: () => void;
  onClear: () => void;
  clearButtonDisabled?: boolean;
}) => {
  return (
    <div className="flex gap-2 px-2 justify-between">
      <Button variant="link" size="sm" onClick={onApply}>
        Apply
      </Button>
      <Button
        variant="linkDestructive"
        size="sm"
        className=""
        onClick={onClear}
        disabled={clearButtonDisabled}
      >
        Clear
      </Button>
    </div>
  );
};
