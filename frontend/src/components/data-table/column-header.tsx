/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column, Table } from "@tanstack/react-table";
import {
  EllipsisIcon,
  FilterIcon,
  MinusIcon,
  TextIcon,
  XIcon,
} from "lucide-react";
import { useRef, useState } from "react";
import { useLocale } from "react-aria";
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
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { capitalize } from "@/utils/strings";
import { Button } from "../ui/button";
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
import { FilterByValuesList } from "./filter-by-values-picker";
import {
  type ColumnFilterForType,
  type ColumnFilterValue,
  Filter,
} from "./filters";
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

interface DataTableColumnHeaderProps<
  TData,
  TValue,
> extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>;
  header: React.ReactNode;
  subheader?: React.ReactNode;
  calculateTopKRows?: CalculateTopKRows;
  table?: Table<TData>;
}

export const DataTableColumnHeader = <TData, TValue>({
  column,
  header,
  subheader,
  className,
  calculateTopKRows,
  table,
}: DataTableColumnHeaderProps<TData, TValue>) => {
  const [isFilterValueOpen, setIsFilterValueOpen] = useState(false);
  const { locale } = useLocale();

  // No header
  if (!header) {
    return null;
  }

  // No sorting or filtering
  if (!column.getCanSort() && !column.getCanFilter()) {
    return (
      <div className={cn(className)}>
        {header}
        {subheader}
      </div>
    );
  }

  const hasFilter = column.getFilterValue() !== undefined;

  return (
    <>
      <div
        className={cn("group flex flex-col my-1 w-full select-none", className)}
      >
        <div className="flex items-center gap-1">
          <span>{header}</span>
          {column.getCanSort() && <SortButton column={column} />}
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
              <DropdownMenuSeparator />
              {renderMenuItemFilter(column)}
              {renderFilterByValues(column, setIsFilterValueOpen)}
              {hasFilter && <ClearFilterMenuItem column={column} />}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {subheader}
      </div>
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
      {renderSortFilterIcon(column)}
    </button>
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
  // Seed local state from the column's existing filter so reopening the
  // picker reflects what's already applied. Preserve `not_in` when present;
  // otherwise default to `in`.
  const existing = column.getFilterValue() as ColumnFilterValue | undefined;
  const isSelectFilter =
    existing && "type" in existing && existing.type === "select";
  const seededOperator: Extract<OperatorType, "in" | "not_in"> =
    isSelectFilter && existing.operator === "not_in" ? "not_in" : "in";
  const seededValues = isSelectFilter ? existing.options : [];

  const [chosenValues, setChosenValues] = useState<Set<unknown>>(
    () => new Set(seededValues),
  );

  const handleApply = () => {
    if (chosenValues.size === 0) {
      column.setFilterValue(undefined);
      return;
    }
    column.setFilterValue(
      Filter.select({
        options: [...chosenValues],
        operator: seededOperator,
      }),
    );
  };

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
      <div className="flex flex-col gap-1.5 py-2">
        <FilterByValuesList
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={chosenValues}
          onChange={(values) => setChosenValues(new Set(values))}
        />
        <FilterButtons
          onApply={handleApply}
          onClear={() => setChosenValues(new Set())}
          clearButtonDisabled={chosenValues.size === 0}
        />
      </div>
    </DraggablePopover>
  );
};
