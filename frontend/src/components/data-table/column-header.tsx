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
import { useMemo, useRef, useState } from "react";
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
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import { Spinner } from "../icons/spinner";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "../ui/popover";
import { loadTableData } from "./utils";
import { Logger } from "@/utils/Logger";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui/table";
import { Checkbox } from "../ui/checkbox";
import { FilterButtons } from "./column-components";

interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>;
  header: React.ReactNode;
  calculateTopKRows?: CalculateTopKRows;
}

export const DataTableColumnHeader = <TData, TValue>({
  column,
  header,
  className,
  calculateTopKRows,
}: DataTableColumnHeaderProps<TData, TValue>) => {
  const [setFilterOpen, setSetFilterOpen] = useState(false);

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
      <FilterButtons
        onApply={handleApply}
        onClear={() => {
          setMin(undefined);
          setMax(undefined);
          column.setFilterValue(undefined);
        }}
        clearButtonDisabled={!hasFilter}
      />
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
      <FilterButtons
        onApply={handleApply}
        onClear={() => {
          setValue("");
          column.setFilterValue(undefined);
        }}
        clearButtonDisabled={!hasFilter}
      />
    </div>
  );
};

const PopoverSetFilter = <TData, TValue>({
  setSetFilterOpen,
  calculateTopKRows,
  column,
}: {
  setSetFilterOpen: (open: boolean) => void;
  calculateTopKRows?: CalculateTopKRows;
  column: Column<TData, TValue>;
}) => {
  const [chosenValues, setChosenValues] = useState<unknown[]>([]);
  const [query, setQuery] = useState<string>("");

  const { data, loading, error } = useAsyncData(async () => {
    if (!calculateTopKRows) {
      return null;
    }
    const res = await calculateTopKRows({ column: column.id, k: 30 });
    return await loadTableData(res.data);
  }, []);

  const filteredData = useMemo(() => {
    if (!data) {
      return [];
    }

    try {
      const typedData = data as Array<Record<string, unknown>>;
      return typedData.filter((row) => {
        const value = row[column.id];
        // Check if value exists and can be converted to string
        // Keep null values for filtering
        return value === undefined
          ? false
          : String(value).toLowerCase().includes(query.toLowerCase());
      });
    } catch (error_) {
      Logger.error("Error filtering data", error_);
      return [];
    }
  }, [data, query, column.id]);

  let dataTable: React.ReactNode;

  if (loading) {
    dataTable = <Spinner size="small" />;
  }

  if (error) {
    dataTable = <ErrorBanner error={error} />;
  }

  // Get all possible keys from the data objects
  // Empty strings may be index
  const keys = [
    ...new Set(
      filteredData
        .flatMap((item) => Object.keys(item))
        .filter((key) => key !== ""),
    ),
  ];

  const handleCheckboxClick = (checked: boolean, value: unknown) => {
    if (!checked) {
      setChosenValues(chosenValues.filter((v) => v !== value));
      return;
    }

    setChosenValues([...chosenValues, value]);
  };

  const handleApply = () => {
    column.setFilterValue(Filter.select(chosenValues));
  };

  if (data) {
    dataTable = (
      <>
        <Table className="w-full border-collapse text-sm overflow-auto block max-h-64">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>{}</TableHead>
              {keys.map((key) => (
                <TableHead key={key} className="text-foreground">
                  {key}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredData.map((row, rowIndex) => {
              const value = row[column.id];
              return (
                <TableRow key={rowIndex}>
                  <TableCell>
                    <Checkbox
                      onCheckedChange={(checked) => {
                        if (typeof checked === "string") {
                          return;
                        }
                        handleCheckboxClick(checked, value);
                      }}
                      aria-label="Select row"
                    />
                  </TableCell>
                  {keys.map((key) => (
                    <TableCell key={`${rowIndex}-${key}`}>
                      {row[key] === null ? "null" : String(row[key])}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        <FilterButtons
          onApply={handleApply}
          onClear={() => {
            setChosenValues([]);
          }}
          clearButtonDisabled={chosenValues.length === 0}
        />
      </>
    );
  }

  return (
    <Popover open={true}>
      <PopoverTrigger />
      <PopoverContent>
        <PopoverClose className="absolute top-2 right-2">
          <Button
            variant="link"
            size="sm"
            onClick={() => setSetFilterOpen(false)}
          >
            X
          </Button>
        </PopoverClose>
        <div className="flex flex-col gap-1.5 pt-1">
          <span className="text-sm font-semibold mx-auto mb-2">Set Filter</span>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search"
            className="my-0 py-1"
            autoFocus={true}
          />
          {dataTable}
        </div>
      </PopoverContent>
    </Popover>
  );
};
