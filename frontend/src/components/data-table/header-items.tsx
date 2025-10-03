/* Copyright 2024 Marimo. All rights reserved. */

import { PinLeftIcon, PinRightIcon } from "@radix-ui/react-icons";
import type { Column, SortingState, Table } from "@tanstack/react-table";
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
  locale: string,
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
          <div className="text-xs text-muted-foreground px-2 py-1">
            Locale: {locale}
          </div>
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
                {formattingExample(option, locale)}
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

export function renderSorts<TData, TValue>(
  column: Column<TData, TValue>,
  table?: Table<TData>,
) {
  if (!column.getCanSort()) {
    return null;
  }

  // If table is available, use full multi-column sort functionality
  if (table) {
    const sortingState: SortingState = table.getState().sorting;
    const currentSort = sortingState.find((s) => s.id === column.id);
    const sortIndex = currentSort
      ? sortingState.indexOf(currentSort) + 1
      : null;

    // Handler to implement stack-based sorting: clicking a sort moves it to the end (highest priority)
    // Clicking the same sort direction again removes it
    const handleSort = (desc: boolean) => {
      if (currentSort && currentSort.desc === desc) {
        // Clicking the same sort again - remove it
        column.clearSorting();
      } else {
        // New sort or different direction - move to end of stack
        const otherSorts = sortingState.filter((s) => s.id !== column.id);
        const newSort = { id: column.id, desc };
        table.setSorting([...otherSorts, newSort]);
      }
    };

    return (
      <>
        <DropdownMenuItem
          onClick={() => handleSort(false)}
          className={
            sortIndex && currentSort && !currentSort.desc ? "bg-accent" : ""
          }
        >
          <AscIcon className="mo-dropdown-icon" />
          Asc
          {sortIndex && currentSort && !currentSort.desc && (
            <span className="ml-auto text-xs font-medium">{sortIndex}</span>
          )}
        </DropdownMenuItem>
        <DropdownMenuItem
          onClick={() => handleSort(true)}
          className={
            sortIndex && currentSort && currentSort.desc ? "bg-accent" : ""
          }
        >
          <DescIcon className="mo-dropdown-icon" />
          Desc
          {sortIndex && currentSort && currentSort.desc && (
            <span className="ml-auto text-xs font-medium">{sortIndex}</span>
          )}
        </DropdownMenuItem>
        {sortingState.length > 1 ? (
          <DropdownMenuItem onClick={() => table.resetSorting()}>
            <ChevronsUpDown className="mo-dropdown-icon" />
            Clear all sorts
          </DropdownMenuItem>
        ) : (
          currentSort && (
            <DropdownMenuItem onClick={() => column.clearSorting()}>
              <ChevronsUpDown className="mo-dropdown-icon" />
              Clear sort
            </DropdownMenuItem>
          )
        )}
        <DropdownMenuSeparator />
      </>
    );
  }

  // Fallback to simple sorting if table not provided
  const isSorted = column.getIsSorted();

  return (
    <>
      <DropdownMenuItem
        onClick={() => column.toggleSorting(false, true)}
        className={isSorted === "asc" ? "bg-accent" : ""}
      >
        <AscIcon className="mo-dropdown-icon" />
        Asc
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={() => column.toggleSorting(true, true)}
        className={isSorted === "desc" ? "bg-accent" : ""}
      >
        <DescIcon className="mo-dropdown-icon" />
        Desc
      </DropdownMenuItem>
      {isSorted && (
        <DropdownMenuItem onClick={() => column.clearSorting()}>
          <ChevronsUpDown className="mo-dropdown-icon" />
          Clear sort
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
