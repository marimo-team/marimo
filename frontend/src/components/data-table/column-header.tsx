/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { Column } from "@tanstack/react-table";
import { FilterIcon, FilterX, MinusIcon, SearchIcon } from "lucide-react";

import { cn } from "@/utils/cn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuPortal,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "../ui/button";
import { useRef, useState } from "react";
import { NumberField } from "../ui/number-field";
import { Input } from "../ui/input";
import { type ColumnFilterForType, Filter } from "./filters";
import { logNever } from "@/utils/assertNever";
import {
  renderColumnPinning,
  renderColumnWrapping,
  renderCopyColumn,
  renderDataType,
  renderFormatOptions,
  renderSortIcon,
  renderSorts,
} from "./header-items";

interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>;
  header: React.ReactNode;
}

export const DataTableColumnHeader = <TData, TValue>({
  column,
  header,
  className,
}: DataTableColumnHeaderProps<TData, TValue>) => {
  // No header
  if (!header) {
    return null;
  }

  // No sorting or filtering
  if (!column.getCanSort() && !column.getCanFilter()) {
    return <div className={cn(className)}>{header}</div>;
  }

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>
        <div
          className={cn(
            "group flex items-center my-1 space-between w-full select-none gap-2 border hover:border-border border-transparent hover:bg-[var(--slate-3)] data-[state=open]:bg-[var(--slate-3)] data-[state=open]:border-border rounded px-1 -mx-1",
            className,
          )}
          data-testid="data-table-sort-button"
        >
          <span className="flex-1">{header}</span>
          <span
            className={cn(
              "h-5 py-1 px-1",
              !column.getIsSorted() &&
                "invisible group-hover:visible data-[state=open]:visible",
            )}
          >
            {renderSortIcon(column)}
          </span>
        </div>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        {renderDataType(column)}
        {renderSorts(column)}
        {renderCopyColumn(column)}
        {renderColumnPinning(column)}
        {renderColumnWrapping(column)}
        {renderFormatOptions(column)}
        <DropdownMenuItemFilter column={column} />
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const DataTableColumnHeaderWithSummary = <TData, TValue>({
  column,
  header,
  summary,
  className,
}: DataTableColumnHeaderProps<TData, TValue> & {
  summary: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        "flex flex-col h-full pt-0.5 pb-3 justify-between items-start",
        className,
      )}
    >
      <DataTableColumnHeader
        column={column}
        header={header}
        className={className}
      />
      {summary}
    </div>
  );
};

export const DropdownMenuItemFilter = <TData, TValue>({
  column,
}: React.PropsWithChildren<{
  column: Column<TData, TValue>;
}>) => {
  const canFilter = column.getCanFilter();
  if (!canFilter) {
    return null;
  }

  const filterType = column.columnDef.meta?.filterType;
  if (!filterType) {
    return null;
  }

  const hasFilter = column.getFilterValue() !== undefined;

  const filterMenuItem = (
    <DropdownMenuSubTrigger>
      <FilterIcon className="mo-dropdown-icon" />
      Filter
    </DropdownMenuSubTrigger>
  );

  const clearFilterMenuItem = (
    <DropdownMenuItem onClick={() => column.setFilterValue(undefined)}>
      <FilterX className="mo-dropdown-icon" />
      Clear filter
    </DropdownMenuItem>
  );

  if (filterType === "boolean") {
    return (
      <>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          {filterMenuItem}
          <DropdownMenuPortal>
            <DropdownMenuSubContent>
              <DropdownMenuItem
                onClick={() => column.setFilterValue(Filter.boolean(true))}
              >
                True
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => column.setFilterValue(Filter.boolean(false))}
              >
                False
              </DropdownMenuItem>
            </DropdownMenuSubContent>
          </DropdownMenuPortal>
        </DropdownMenuSub>
        {hasFilter && clearFilterMenuItem}
      </>
    );
  }

  if (filterType === "text") {
    return (
      <>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          {filterMenuItem}
          <DropdownMenuPortal>
            <DropdownMenuSubContent>
              <TextFilter column={column} />
            </DropdownMenuSubContent>
          </DropdownMenuPortal>
        </DropdownMenuSub>
        {hasFilter && clearFilterMenuItem}
      </>
    );
  }

  if (filterType === "number") {
    return (
      <>
        <DropdownMenuSeparator />
        <DropdownMenuSub>
          {filterMenuItem}
          <DropdownMenuPortal>
            <DropdownMenuSubContent>
              <NumberRangeFilter column={column} />
            </DropdownMenuSubContent>
          </DropdownMenuPortal>
        </DropdownMenuSub>
        {hasFilter && clearFilterMenuItem}
      </>
    );
  }

  if (filterType === "select") {
    // Not implemented
    return null;
  }

  if (filterType === "time") {
    // Not implemented
    return null;
  }

  if (filterType === "datetime") {
    // Not implemented
    return null;
  }

  if (filterType === "date") {
    // Not implemented
    return null;
  }

  logNever(filterType);
  return null;
};

const NumberRangeFilter = <TData, TValue>({
  column,
}: {
  column: Column<TData, TValue>;
}) => {
  const currentFilter = column.getFilterValue() as
    | ColumnFilterForType<"number">
    | undefined;
  const hasFilter = currentFilter !== undefined;

  const [min, setMin] = useState<number | undefined>(currentFilter?.min);
  const [max, setMax] = useState<number | undefined>(currentFilter?.max);
  const minRef = useRef<HTMLInputElement>(null);
  const maxRef = useRef<HTMLInputElement>(null);

  const handleApply = (opts: { min?: number; max?: number } = {}) => {
    column.setFilterValue(
      Filter.number({
        min: opts.min ?? min,
        max: opts.max ?? max,
      }),
    );
  };

  return (
    <div className="flex flex-col gap-1 pt-3 px-2">
      <div className="flex gap-1 items-center">
        <NumberField
          ref={minRef}
          value={min}
          onChange={(value) => setMin(value)}
          placeholder="min"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleApply({ min: Number.parseFloat(e.currentTarget.value) });
            }
            if (e.key === "Tab") {
              maxRef.current?.focus();
            }
          }}
          className="shadow-none! border-border hover:shadow-none!"
        />
        <MinusIcon className="h-5 w-5 text-muted-foreground" />
        <NumberField
          ref={maxRef}
          value={max}
          onChange={(value) => setMax(value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleApply({ max: Number.parseFloat(e.currentTarget.value) });
            }
            if (e.key === "Tab") {
              minRef.current?.focus();
            }
          }}
          placeholder="max"
          className="shadow-none! border-border hover:shadow-none!"
        />
      </div>
      <div className="flex gap-2 px-2 justify-between">
        <Button variant="link" size="sm" onClick={() => handleApply()}>
          Apply
        </Button>
        <Button
          variant="linkDestructive"
          size="sm"
          disabled={!hasFilter}
          className=""
          onClick={() => {
            setMin(undefined);
            setMax(undefined);
            column.setFilterValue(undefined);
          }}
        >
          Clear
        </Button>
      </div>
    </div>
  );
};

const TextFilter = <TData, TValue>({
  column,
}: {
  column: Column<TData, TValue>;
}) => {
  const currentFilter = column.getFilterValue() as
    | ColumnFilterForType<"text">
    | undefined;
  const hasFilter = currentFilter !== undefined;
  const [value, setValue] = useState<string>(currentFilter?.text ?? "");

  const handleApply = () => {
    if (value === "") {
      column.setFilterValue(undefined);
      return;
    }
    column.setFilterValue(Filter.text(value));
  };

  return (
    <div className="flex flex-col gap-1 pt-3 px-2">
      <Input
        type="text"
        icon={<SearchIcon className="h-3 w-3 text-muted-foreground" />}
        value={value ?? ""}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Search"
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            handleApply();
          }
        }}
        className="shadow-none! border-border hover:shadow-none!"
      />
      <div className="flex gap-2 px-2 justify-between">
        <Button variant="link" size="sm" onClick={() => handleApply()}>
          Apply
        </Button>
        <Button
          variant="linkDestructive"
          size="sm"
          disabled={!hasFilter}
          className=""
          onClick={() => {
            setValue("");
            column.setFilterValue(undefined);
          }}
        >
          Clear
        </Button>
      </div>
    </div>
  );
};
