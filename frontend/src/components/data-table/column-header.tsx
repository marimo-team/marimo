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
import { useState } from "react";
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
import { Button } from "../ui/button";
import { DraggablePopover } from "../ui/draggable-popover";
import { Input } from "../ui/input";
import { RegexInput } from "./regex-input";
import { NumberField } from "../ui/number-field";
import { PopoverClose } from "../ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { FilterByValuesList } from "./filter-by-values-picker";
import { OPERATOR_LABELS } from "./operator-labels";
import {
  type ColumnFilterForType,
  type ColumnFilterValue,
  DATETIME_OPS,
  Filter,
  isDatetimeComparisonOp,
  isNumberComparisonOp,
  isTextScalarOp,
  NUMBER_OPS,
  TEXT_OPS,
} from "./filters";
import {
  type DateLikeFilterType,
  DateLikeInput,
  DateLikeRangeInput,
} from "./date-filter-inputs";
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

  return (
    <>
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
              <span>{header}</span>
            </>
          ) : (
            <>
              <span>{header}</span>
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
              <DropdownMenuSeparator />
              {renderMenuItemFilter(column, calculateTopKRows)}
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
  calculateTopKRows?: CalculateTopKRows,
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
            <TextFilterMenu
              column={column}
              calculateTopKRows={calculateTopKRows}
            />
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
            <NumberFilterMenu column={column} />
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
    );
  }

  if (filterType === "select") {
    // Not implemented
    return null;
  }

  if (
    filterType === "date" ||
    filterType === "datetime" ||
    filterType === "time"
  ) {
    return (
      <DropdownMenuSub>
        {filterMenuItem}
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <DateFilterMenu column={column} filterType={filterType} />
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
    );
  }

  logNever(filterType);
  return null;
}

const OperatorSelect = ({
  operator,
  options,
  onChange,
}: {
  operator: OperatorType;
  options: readonly OperatorType[];
  onChange: (next: OperatorType) => void;
}) => (
  <Select value={operator} onValueChange={(v) => onChange(v as OperatorType)}>
    <SelectTrigger className="border-border shadow-none! ring-0! w-full mb-0.5">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {options.map((op) => (
        <SelectItem key={op} value={op}>
          {OPERATOR_LABELS[op]}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

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

type NumberComparisonFilter = Extract<
  ColumnFilterForType<"number">,
  { value: number }
>;
const isNumberComparisonFilter = (
  filter: ColumnFilterForType<"number">,
): filter is NumberComparisonFilter => isNumberComparisonOp(filter.operator);

export const NumberFilterMenu = <TData, TValue>({
  column,
}: {
  column: Column<TData, TValue>;
}) => {
  const currentFilter = column.getFilterValue() as
    | ColumnFilterForType<"number">
    | undefined;
  const hasFilter = currentFilter !== undefined;

  const [operator, setOperator] = useState<OperatorType>(
    currentFilter?.operator ?? "between",
  );
  const [min, setMin] = useState<number | undefined>(
    currentFilter?.operator === "between" ? currentFilter.min : undefined,
  );
  const [max, setMax] = useState<number | undefined>(
    currentFilter?.operator === "between" ? currentFilter.max : undefined,
  );
  const [value, setValue] = useState<number | undefined>(
    currentFilter !== undefined && isNumberComparisonFilter(currentFilter)
      ? currentFilter.value
      : undefined,
  );

  const isComparison = isNumberComparisonOp(operator);
  const isNullish = operator === "is_null" || operator === "is_not_null";

  const applyDisabled =
    (operator === "between" && (min === undefined || max === undefined)) ||
    (isComparison && value === undefined);

  const handleApply = () => {
    if (isNullish) {
      column.setFilterValue(Filter.number({ operator }));
      return;
    }
    if (operator === "between" && min !== undefined && max !== undefined) {
      column.setFilterValue(Filter.number({ operator: "between", min, max }));
      return;
    }
    if (isComparison && value !== undefined) {
      column.setFilterValue(Filter.number({ operator, value }));
    }
  };

  const handleClear = () => {
    setMin(undefined);
    setMax(undefined);
    setValue(undefined);
    column.setFilterValue(undefined);
  };

  const handleOperatorChange = (next: OperatorType) => {
    setOperator(next);
  };

  return (
    <div className="flex flex-col gap-1 pt-3 px-2">
      <OperatorSelect
        operator={operator}
        options={NUMBER_OPS}
        onChange={handleOperatorChange}
      />
      {operator === "between" && (
        <div className="flex gap-1 items-center">
          <NumberField
            value={min}
            onChange={setMin}
            aria-label="min"
            placeholder="min"
            className="shadow-none! border-border hover:shadow-none!"
          />
          <MinusIcon className="h-5 w-5 text-muted-foreground" />
          <NumberField
            value={max}
            onChange={setMax}
            aria-label="max"
            placeholder="max"
            className="shadow-none! border-border hover:shadow-none!"
          />
        </div>
      )}
      {isComparison && (
        <NumberField
          value={value}
          onChange={setValue}
          aria-label="value"
          placeholder="value"
          className="shadow-none! border-border hover:shadow-none!"
        />
      )}
      <FilterButtons
        onApply={handleApply}
        onClear={handleClear}
        clearButtonDisabled={!hasFilter}
        applyButtonDisabled={applyDisabled}
      />
    </div>
  );
};

type DateComparisonFilter = Extract<
  ColumnFilterForType<DateLikeFilterType>,
  { value: Date }
>;
const isDateComparisonFilter = (
  filter: ColumnFilterForType<DateLikeFilterType>,
): filter is DateComparisonFilter => isDatetimeComparisonOp(filter.operator);

export const DateFilterMenu = <TData, TValue>({
  column,
  filterType,
}: {
  column: Column<TData, TValue>;
  filterType: DateLikeFilterType;
}) => {
  const currentFilter = column.getFilterValue() as
    | ColumnFilterForType<DateLikeFilterType>
    | undefined;
  const hasFilter = currentFilter !== undefined;

  const [operator, setOperator] = useState<OperatorType>(
    currentFilter?.operator ?? "between",
  );
  const [min, setMin] = useState<Date | undefined>(
    currentFilter?.operator === "between" ? currentFilter.min : undefined,
  );
  const [max, setMax] = useState<Date | undefined>(
    currentFilter?.operator === "between" ? currentFilter.max : undefined,
  );
  const [value, setValue] = useState<Date | undefined>(
    currentFilter !== undefined && isDateComparisonFilter(currentFilter)
      ? currentFilter.value
      : undefined,
  );

  const isComparison = isDatetimeComparisonOp(operator);
  const isNullish = operator === "is_null" || operator === "is_not_null";

  const applyDisabled =
    (operator === "between" && (min === undefined || max === undefined)) ||
    (isComparison && value === undefined);

  const buildFilter = (
    opts: Parameters<typeof Filter.date>[0],
  ): ColumnFilterForType<DateLikeFilterType> => {
    switch (filterType) {
      case "date":
        return Filter.date(opts);
      case "datetime":
        return Filter.datetime(opts);
      case "time":
        return Filter.time(opts);
    }
  };

  const handleApply = () => {
    if (isNullish) {
      column.setFilterValue(buildFilter({ operator }));
      return;
    }
    if (operator === "between" && min !== undefined && max !== undefined) {
      column.setFilterValue(buildFilter({ operator: "between", min, max }));
      return;
    }
    if (isComparison && value !== undefined) {
      column.setFilterValue(buildFilter({ operator, value }));
    }
  };

  const handleClear = () => {
    setMin(undefined);
    setMax(undefined);
    setValue(undefined);
    column.setFilterValue(undefined);
  };

  const handleOperatorChange = (next: OperatorType) => {
    setOperator(next);
  };

  return (
    <div
      className="flex flex-col gap-1 pt-3 px-2"
      onKeyDownCapture={(e) => {
        if (e.key === "Tab") {
          e.stopPropagation();
        }
      }}
    >
      <OperatorSelect
        operator={operator}
        options={DATETIME_OPS}
        onChange={handleOperatorChange}
      />
      {operator === "between" && (
        <DateLikeRangeInput
          filterType={filterType}
          min={min}
          max={max}
          onMinChange={setMin}
          onMaxChange={setMax}
          className="shadow-none! border-border hover:shadow-none!"
        />
      )}
      {isComparison && (
        <DateLikeInput
          filterType={filterType}
          value={value}
          onChange={setValue}
          aria-label="value"
          className="shadow-none! border-border hover:shadow-none!"
        />
      )}
      <FilterButtons
        onApply={handleApply}
        onClear={handleClear}
        clearButtonDisabled={!hasFilter}
        applyButtonDisabled={applyDisabled}
      />
    </div>
  );
};

export const TextFilterMenu = <TData, TValue>({
  column,
  calculateTopKRows,
}: {
  column: Column<TData, TValue>;
  calculateTopKRows?: CalculateTopKRows;
}) => {
  const currentFilter = column.getFilterValue() as
    | ColumnFilterForType<"text">
    | undefined;
  const hasFilter = currentFilter !== undefined;

  const [operator, setOperator] = useState<OperatorType>(
    currentFilter?.operator ?? "contains",
  );
  const [text, setText] = useState<string>(
    currentFilter && "text" in currentFilter ? currentFilter.text : "",
  );
  const [values, setValues] = useState<string[]>(
    currentFilter && "values" in currentFilter ? [...currentFilter.values] : [],
  );

  const isScalar = isTextScalarOp(operator);
  const isMulti = operator === "in" || operator === "not_in";
  const isNullish =
    operator === "is_null" ||
    operator === "is_not_null" ||
    operator === "is_empty";

  const applyDisabled =
    (isScalar && text === "") || (isMulti && values.length === 0);

  const handleApply = () => {
    if (isNullish) {
      column.setFilterValue(Filter.text({ operator }));
      return;
    }
    if (isScalar && text !== "") {
      column.setFilterValue(Filter.text({ operator, text }));
      return;
    }
    if (isMulti && values.length > 0) {
      column.setFilterValue(Filter.text({ operator, values }));
    }
  };

  const handleClear = () => {
    setText("");
    setValues([]);
    column.setFilterValue(undefined);
  };

  const handleOperatorChange = (next: OperatorType) => {
    setOperator(next);
  };

  return (
    <div className="flex flex-col gap-1 pt-3 px-2">
      <OperatorSelect
        operator={operator}
        options={TEXT_OPS}
        onChange={handleOperatorChange}
      />
      {isScalar && operator === "regex" && (
        <RegexInput
          value={text}
          onChange={setText}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") {
              handleApply();
            }
          }}
        />
      )}
      {isScalar && operator !== "regex" && (
        <Input
          type="text"
          icon={<TextIcon className="h-3 w-3 text-muted-foreground mb-1" />}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Text..."
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter") {
              handleApply();
            }
          }}
          className="shadow-none! border-border hover:shadow-none!"
        />
      )}
      {isMulti && (
        <FilterByValuesList
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={new Set(values)}
          onChange={(next) => setValues(next.map(String))}
          creatable={true}
        />
      )}
      <FilterButtons
        onApply={handleApply}
        onClear={handleClear}
        clearButtonDisabled={!hasFilter}
        applyButtonDisabled={applyDisabled}
      />
    </div>
  );
};

/**
 * Seed the filter-by-values picker from a column's existing filter value.
 *
 * Reopening the picker should reflect what's already applied. Only `select`
 * filters carry checkbox-style values; other filter shapes (number, text,
 * etc.) seed an empty list.
 */
export function seedFromFilter(value: ColumnFilterValue | undefined): {
  values: unknown[];
  operator: Extract<OperatorType, "in" | "not_in">;
} {
  if (value && "type" in value && value.type === "select") {
    return {
      values: [...value.options],
      operator: value.operator === "not_in" ? "not_in" : "in",
    };
  }
  return { values: [], operator: "in" };
}

const PopoverFilterByValues = <TData, TValue>({
  setIsFilterValueOpen,
  calculateTopKRows,
  column,
}: {
  setIsFilterValueOpen: (open: boolean) => void;
  calculateTopKRows?: CalculateTopKRows;
  column: Column<TData, TValue>;
}) => {
  const seed = seedFromFilter(
    column.getFilterValue() as ColumnFilterValue | undefined,
  );

  const [chosenValues, setChosenValues] = useState<Set<unknown>>(
    () => new Set(seed.values),
  );

  const handleApply = () => {
    if (chosenValues.size === 0) {
      column.setFilterValue(undefined);
      return;
    }
    column.setFilterValue(
      Filter.select({
        options: [...chosenValues],
        operator: seed.operator,
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
