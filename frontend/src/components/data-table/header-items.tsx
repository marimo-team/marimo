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
  ArrowDownNarrowWideIcon,
  ArrowDownWideNarrowIcon,
} from "lucide-react";
import { copyToClipboard } from "@/utils/copy";
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

export function renderCopyColumnId<TData, TValue>(
  column: Column<TData, TValue>,
) {
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

const AscIcon = ArrowDownNarrowWideIcon;
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

export function renderSortIcon<TData, TValue>(column: Column<TData, TValue>) {
  if (!column.getCanSort()) {
    return null;
  }

  const isSorted = column.getIsSorted();

  return isSorted === "desc" ? (
    <DescIcon className="h-3 w-3" />
  ) : isSorted === "asc" ? (
    <AscIcon className="h-3 w-3" />
  ) : (
    <ChevronsUpDown className="h-3 w-3" />
  );
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
