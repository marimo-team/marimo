/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type { Column } from "@tanstack/react-table";
import { capitalize } from "lodash-es";
import { FilterIcon, MinusIcon, TextIcon, XIcon } from "lucide-react";
import { useMemo, useRef, useState } from "react";
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
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "@/plugins/impl/common/error-banner";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { Spinner } from "../icons/spinner";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "../ui/command";
import { DraggablePopover } from "../ui/draggable-popover";
import { Input } from "../ui/input";
import { NumberField } from "../ui/number-field";
import { PopoverClose } from "../ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { type ColumnFilterForType, Filter } from "./filters";
import {
  ClearFilterMenuItem,
  FilterButtons,
  renderColumnPinning,
  renderColumnWrapping,
  renderCopyColumn,
  renderDataType,
  renderFilterByValues,
  renderFormatOptions,
  renderSortFilterIcon,
  renderSorts,
} from "./header-items";
import { renderUnknownValue } from "./renderers";

const TOP_K_ROWS = 30;

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
  const [isFilterValueOpen, setIsFilterValueOpen] = useState(false);

  // No header
  if (!header) {
    return null;
  }

  // No sorting or filtering
  if (!column.getCanSort() && !column.getCanFilter()) {
    return <div className={cn(className)}>{header}</div>;
  }

  const hasFilter = column.getFilterValue() !== undefined;
  const hideIcon = !column.getIsSorted() && !hasFilter;

  return (
    <>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild={true}>
          <div
            className={cn(
              "group flex items-center my-1 space-between w-full select-none gap-2 border hover:border-border border-transparent hover:bg-(--slate-3) data-[state=open]:bg-(--slate-3) data-[state=open]:border-border rounded px-1 -mx-1",
              className,
            )}
            data-testid="data-table-sort-button"
          >
            <span className="flex-1">{header}</span>
            <span
              className={cn(
                "h-5 py-1 px-1",
                hideIcon &&
                  "invisible group-hover:visible data-[state=open]:visible",
              )}
            >
              {renderSortFilterIcon(column)}
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
          <DropdownMenuSeparator />
          {renderMenuItemFilter(column)}
          {renderFilterByValues(column, setIsFilterValueOpen)}
          {hasFilter && <ClearFilterMenuItem column={column} />}
        </DropdownMenuContent>
      </DropdownMenu>
      {isFilterValueOpen && (
        <PopoverFilterByValues
          setIsFilterValueOpen={setIsFilterValueOpen}
          calculateTopKRows={calculateTopKRows}
          column={column}
        />
      )}
    </>
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

export function renderMenuItemFilter<TData, TValue>(
  column: Column<TData, TValue>,
) {
  const canFilter = column.getCanFilter();
  if (!canFilter) {
    return null;
  }

  const filterType = column.columnDef.meta?.filterType;
  if (!filterType) {
    return null;
  }

  const filterMenuItem = (
    <DropdownMenuSubTrigger>
      <FilterIcon className="mo-dropdown-icon" />
      Filter
    </DropdownMenuSubTrigger>
  );

  if (filterType === "boolean") {
    return (
      <DropdownMenuSub>
        {filterMenuItem}
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <BooleanFilter column={column} />
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
    );
  }

  if (filterType === "text") {
    return (
      <DropdownMenuSub>
        {filterMenuItem}
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <TextFilter column={column} />
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
    );
  }

  if (filterType === "number") {
    return (
      <DropdownMenuSub>
        {filterMenuItem}
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <NumberRangeFilter column={column} />
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
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
}

// Type-safe constants for null filter operators
const NULL_FILTER_OPERATORS = {
  is_null: "is_null",
  is_not_null: "is_not_null",
} satisfies Record<string, OperatorType>;

const NullFilter = <TData, TValue>({
  column,
  defaultItem,
  operator,
  setOperator,
}: {
  column: Column<TData, TValue>;
  defaultItem?: OperatorType | "between";
  operator: OperatorType | "between";
  setOperator: (operator: OperatorType) => void;
}) => {
  const handleValueChange = (value: OperatorType) => {
    setOperator(value);
    if (value === "is_null" || value === "is_not_null") {
      column.setFilterValue(Filter.text({ operator: value }));
    }
  };

  const isNullOrNotNull = operator === "is_null" || operator === "is_not_null";

  return (
    <Select
      value={operator}
      onValueChange={(value) => handleValueChange(value as OperatorType)}
    >
      <SelectTrigger
        className={cn(
          "border-border shadow-none! ring-0! w-full mb-0.5",
          isNullOrNotNull && "mb-2",
        )}
      >
        <SelectValue defaultValue={operator} />
      </SelectTrigger>
      <SelectContent>
        {defaultItem && (
          <SelectItem value={defaultItem}>{capitalize(defaultItem)}</SelectItem>
        )}
        <SelectSeparator />
        <SelectItem value={NULL_FILTER_OPERATORS.is_null}>Is null</SelectItem>
        <SelectItem value={NULL_FILTER_OPERATORS.is_not_null}>
          Is not null
        </SelectItem>
      </SelectContent>
    </Select>
  );
};

const BooleanFilter = <TData, TValue>({
  column,
}: {
  column: Column<TData, TValue>;
}) => {
  return (
    <>
      <DropdownMenuItem
        onClick={() =>
          column.setFilterValue(
            Filter.boolean({ value: true, operator: "is_true" }),
          )
        }
      >
        True
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={() =>
          column.setFilterValue(
            Filter.boolean({ value: false, operator: "is_false" }),
          )
        }
      >
        False
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem
        onClick={() =>
          column.setFilterValue(Filter.boolean({ operator: "is_null" }))
        }
      >
        Is null
      </DropdownMenuItem>
      <DropdownMenuItem
        onClick={() =>
          column.setFilterValue(Filter.boolean({ operator: "is_not_null" }))
        }
      >
        Is not null
      </DropdownMenuItem>
    </>
  );
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

  const [operator, setOperator] = useState<OperatorType | "between">(
    currentFilter?.operator ?? "between",
  );
  const [min, setMin] = useState<number | undefined>(currentFilter?.min);
  const [max, setMax] = useState<number | undefined>(currentFilter?.max);
  const minRef = useRef<HTMLInputElement>(null);
  const maxRef = useRef<HTMLInputElement>(null);

  const handleApply = (opts: { min?: number; max?: number } = {}) => {
    column.setFilterValue(
      Filter.number({
        min: opts.min ?? min,
        max: opts.max ?? max,
        operator: operator === "between" ? undefined : operator,
      }),
    );
  };

  return (
    <div className="flex flex-col gap-1 pt-3 px-2">
      <NullFilter
        column={column}
        defaultItem="between"
        operator={operator}
        setOperator={setOperator}
      />
      {operator === "between" && (
        <>
          <div className="flex gap-1 items-center">
            <NumberField
              ref={minRef}
              value={min}
              onChange={(value) => setMin(value)}
              aria-label="min"
              placeholder="min"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleApply({
                    min: Number.parseFloat(e.currentTarget.value),
                  });
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
                  handleApply({
                    max: Number.parseFloat(e.currentTarget.value),
                  });
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
        </>
      )}
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
  const [operator, setOperator] = useState<OperatorType>(
    currentFilter?.operator ?? "contains",
  );

  const handleApply = () => {
    if (operator !== "contains") {
      column.setFilterValue(Filter.text({ operator }));
      return;
    }

    if (value === "") {
      column.setFilterValue(undefined);
      return;
    }

    column.setFilterValue(Filter.text({ text: value, operator }));
  };

  return (
    <div className="flex flex-col gap-1 pt-3 px-2">
      <NullFilter
        column={column}
        defaultItem="contains"
        operator={operator}
        setOperator={setOperator}
      />
      {operator === "contains" && (
        <>
          <Input
            type="text"
            icon={<TextIcon className="h-3 w-3 text-muted-foreground mb-1" />}
            value={value ?? ""}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Text..."
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
        </>
      )}
    </div>
  );
};

const PopoverFilterByValues = <TData, TValue>({
  setIsFilterValueOpen,
  calculateTopKRows,
  column,
}: {
  setIsFilterValueOpen: (open: boolean) => void;
  calculateTopKRows?: CalculateTopKRows;
  column: Column<TData, TValue>;
}) => {
  const [chosenValues, setChosenValues] = useState<Set<unknown>>(new Set());
  const [query, setQuery] = useState<string>("");

  const { data, isPending, error } = useAsyncData(async () => {
    if (!calculateTopKRows) {
      return null;
    }
    const res = await calculateTopKRows({ column: column.id, k: TOP_K_ROWS });
    return res.data;
  }, []);

  const filteredData = useMemo(() => {
    if (!data) {
      return [];
    }

    try {
      return data.filter(([value, _count]) => {
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
  }, [data, query]);

  let dataTable: React.ReactNode;

  if (isPending) {
    dataTable = <Spinner size="medium" className="mx-auto mt-12 mb-10" />;
  }

  if (error) {
    dataTable = <ErrorBanner error={error} className="my-10 mx-4" />;
  }

  const handleToggle = (value: unknown) => {
    setChosenValues((prev) => {
      const checked = prev.has(value);
      const newSet = new Set(prev);
      if (checked) {
        newSet.delete(value);
      } else {
        newSet.add(value);
      }
      return newSet;
    });
  };

  const handleToggleAll = (checked: boolean) => {
    if (!data) {
      return;
    }
    if (checked) {
      setChosenValues(new Set(filteredData.map(([value]) => value)));
    } else {
      setChosenValues(new Set());
    }
  };

  const handleApply = () => {
    if (chosenValues.size === 0) {
      column.setFilterValue(undefined);
      return;
    }
    column.setFilterValue(
      Filter.select({ options: [...chosenValues], operator: "in" }),
    );
  };

  if (data) {
    const allChecked = chosenValues.size === filteredData.length;

    dataTable = (
      <>
        <Command className="text-sm outline-hidden" shouldFilter={false}>
          <CommandInput
            placeholder="Search"
            autoFocus={true}
            onValueChange={(value) => setQuery(value.trim())}
          />
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandList className="border-b">
            {filteredData.length > 0 && (
              <CommandItem
                value="__select-all__"
                className="border-b rounded-none px-3"
                onSelect={() => handleToggleAll(!allChecked)}
              >
                <Checkbox
                  checked={chosenValues.size === filteredData.length}
                  aria-label="Select all"
                  className="mr-3 h-3.5 w-3.5"
                />
                <span className="font-bold flex-1">{column.id}</span>
                <span className="font-bold">Count</span>
              </CommandItem>
            )}
            {filteredData.map(([value, count], rowIndex) => {
              const isSelected = chosenValues.has(value);
              const valueString = renderUnknownValue({ value });

              return (
                <CommandItem
                  key={rowIndex}
                  value={valueString}
                  className="not-last:border-b rounded-none px-3"
                  onSelect={() => handleToggle(value)}
                >
                  <Checkbox
                    checked={isSelected}
                    aria-label="Select row"
                    className="mr-3 h-3.5 w-3.5"
                  />
                  <span className="flex-1 overflow-hidden max-h-20 line-clamp-3">
                    {valueString}
                  </span>
                  <span className="ml-3">{count}</span>
                </CommandItem>
              );
            })}
          </CommandList>
          {filteredData.length === TOP_K_ROWS && (
            <span className="text-xs text-muted-foreground mt-1.5 text-center">
              Only showing the top {TOP_K_ROWS} values
            </span>
          )}
        </Command>
        <FilterButtons
          onApply={handleApply}
          onClear={() => {
            setChosenValues(new Set());
          }}
          clearButtonDisabled={chosenValues.size === 0}
        />
      </>
    );
  }

  return (
    <DraggablePopover
      open={true}
      onOpenChange={(open) => !open && setIsFilterValueOpen(false)}
      className="w-80 p-0"
    >
      <PopoverClose className="absolute top-2 right-2">
        <Button
          variant="link"
          size="sm"
          onClick={() => setIsFilterValueOpen(false)}
        >
          <XIcon className="h-4 w-4" />
        </Button>
      </PopoverClose>
      <div className="flex flex-col gap-1.5 py-2">{dataTable}</div>
    </DraggablePopover>
  );
};
