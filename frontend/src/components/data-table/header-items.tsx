/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import {
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
} from "@/components/ui/dropdown-menu";
import { DATA_TYPE_ICON } from "../datasets/icons";
import { formattingExample } from "./column-formatting/feature";
import { formatOptions } from "./column-formatting/types";
import type { Column } from "@tanstack/react-table";
import type { DataType } from "@/core/kernel/messages";
import { PinLeftIcon, PinRightIcon } from "@radix-ui/react-icons";
import {
  AlignJustifyIcon,
  WrapTextIcon,
  PinOffIcon,
  CopyIcon,
  ChevronsUpDown,
  ArrowDownWideNarrowIcon,
  FilterX,
  ArrowUpNarrowWideIcon,
  ListFilterPlusIcon,
  FunnelPlusIcon,
  ListFilterIcon,
} from "lucide-react";
import { copyToClipboard } from "@/utils/copy";
import { NAMELESS_COLUMN_PREFIX } from "./columns";
import { Button } from "../ui/button";

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

export function renderSorts<TData, TValue>(column: Column<TData, TValue>) {
  if (!column.getCanSort()) {
    return null;
  }

  return (
    <>
      <DropdownMenuItem onClick={() => column.toggleSorting(false)}>
        <AscIcon className="mo-dropdown-icon" />
        Asc
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => column.toggleSorting(true)}>
        <DescIcon className="mo-dropdown-icon" />
        Desc
      </DropdownMenuItem>
      {column.getIsSorted() && (
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
