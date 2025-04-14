/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { Column, ColumnFiltersState } from "@tanstack/react-table";
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
import { memo, useRef, useState } from "react";
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
import type {
  SetFilters,
  CalculateTopKRows,
} from "@/plugins/impl/DataTablePlugin";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { Spinner } from "../icons/spinner";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "../ui/popover";
import { loadData } from "./utils";
import { Logger } from "@/utils/Logger";

interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>;
  header: React.ReactNode;
  calculateTopKRows?: CalculateTopKRows;
  filters?: ColumnFiltersState;
  setFilters?: SetFilters;
}

export const DataTableColumnHeader = <TData, TValue>({
  column,
  header,
  className,
  calculateTopKRows,
  filters,
  setFilters,
}: DataTableColumnHeaderProps<TData, TValue>) => {
  const [localFilterOpen, setLocalFilterOpen] = useState(false);

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
          aria-label="min"
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
          aria-label="max"
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

// TODO: This is triggering immediately, which is not what we want
const PopoverLocalFilter = <TData, TValue>({
  setLocalFilterOpen,
  calculateTopKRows,
  filters,
  setFilters,
  column,
}: {
  setLocalFilterOpen: (open: boolean) => void;
  calculateTopKRows?: CalculateTopKRows;
  column: Column<TData, TValue>;
  filters?: ColumnFiltersState;
  setFilters?: SetFilters;
}) => {
  // const [filterValues, setFilterValues] = useState<
  //   ColumnFiltersState | undefined
  // >(filters);
  const { data, loading, error } = useAsyncData(async () => {
    if (!calculateTopKRows) {
      return null;
    }
    const res = await calculateTopKRows({ column: column.id, k: 10 });
    return await loadData(res.data);
  }, []);

  let dataTable: React.ReactNode;

  if (loading) {
    dataTable = <Spinner size="small" />;
  }

  if (error) {
    dataTable = <ErrorBanner error={error} />;
  }

  if (!data) {
    return null;
  }

  // Type assertion to handle the data array
  const typedData = data as Array<Record<string, unknown>>;

  // Get all possible keys from the data objects
  const keys = [...new Set(typedData.flatMap((item) => Object.keys(item)))];

  const handleCheckboxClick = (value: unknown) => {
    if (!setFilters) {
      Logger.error("No setFilters function provided");
      return;
    }

    // Get the filter type from the column definition
    const filterType = column.columnDef.meta?.filterType;
    if (!filterType) {
      Logger.error("No filter type defined for column");
      return;
    }

    // Create the appropriate filter based on the filter type
    let filterValue: any;
    switch (filterType) {
      case "boolean":
        filterValue = Filter.boolean(value as boolean);
        break;
      case "number":
        filterValue = Filter.number({ min: value as number });
        break;
      case "text":
        filterValue = Filter.text(String(value));
        break;
      default:
        Logger.error("Unsupported filter type:", filterType);
        return;
    }

    setFilters([
      ...(filters ?? []),
      {
        id: column.id,
        value: filterValue,
      },
    ]);
  };

  return (
    <Popover open={true}>
      <PopoverTrigger />
      <PopoverContent>
        <PopoverClose className="absolute top-2 right-2">
          <Button
            variant="link"
            size="sm"
            onClick={() => setLocalFilterOpen(false)}
          >
            Close
          </Button>
        </PopoverClose>
        <div className="flex flex-col gap-1.5 pt-1">
          <span className="text-sm font-semibold mx-auto">Local Filter</span>
          <div className="overflow-auto max-h-60">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b">
                  <th className="px-2 py-1 text-left font-medium">{}</th>
                  {keys.map((key) => (
                    <th key={key} className="px-2 py-1 text-left font-medium">
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {typedData.map((row, rowIndex) => {
                  const value = row[column.id];
                  return (
                    <tr
                      key={rowIndex}
                      className="border-b border-gray-100 hover:bg-gray-50"
                    >
                      <td key={rowIndex} className="px-2 py-1">
                        <input
                          type="checkbox"
                          onClick={() => handleCheckboxClick(value)}
                        />
                      </td>
                      {keys.map((key) => (
                        <td key={`${rowIndex}-${key}`} className="px-2 py-1">
                          {row[key] === null ? "null" : String(row[key])}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
};
