/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { ColumnFiltersState, Table } from "@tanstack/react-table";
import { XIcon } from "lucide-react";
import { useState } from "react";
import { type DateFormatter, useDateFormatter } from "react-aria";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "../ui/popover";
import { FilterPillEditor } from "./filter-pill-editor";
import type { ColumnFilterValue } from "./filters";
import { stringifyUnknownValue } from "./utils";

interface Props<TData> {
  filters: ColumnFiltersState | undefined;
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
}

export const FilterPills = <TData,>({
  filters,
  table,
  calculateTopKRows,
}: Props<TData>) => {
  const timeFormatter = useDateFormatter({
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  if (!filters || filters.length === 0) {
    return null;
  }

  return (
    <div part="filter-pills" className="flex flex-wrap gap-2 px-1 py-2">
      {filters.map((filter) => (
        <FilterPill
          key={filter.id}
          columnId={filter.id}
          value={filter.value as ColumnFilterValue}
          timeFormatter={timeFormatter}
          table={table}
          calculateTopKRows={calculateTopKRows}
          onRemove={() =>
            table.setColumnFilters((filters) =>
              filters.filter((f) => f.id !== filter.id),
            )
          }
        />
      ))}
    </div>
  );
};

interface FilterPillProps<TData> {
  columnId: string;
  value: ColumnFilterValue;
  timeFormatter: DateFormatter;
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
  onRemove: () => void;
}

const FilterPill = <TData,>({
  columnId,
  value,
  timeFormatter,
  table,
  calculateTopKRows,
  onRemove,
}: FilterPillProps<TData>) => {
  const [open, setOpen] = useState(false);

  const formatted = formatValue(value, timeFormatter);
  if (!formatted) {
    return null;
  }

  // this is temporary, with more operator & datatype support this goes away
  const isReadOnly =
    "type" in value &&
    (value.type === "date" ||
      value.type === "datetime" ||
      value.type === "time");

  const twoSegment = formatted.value === undefined;

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRemove();
  };

  const segments = (
    <>
      <span className="text-foreground">{columnId}</span>
      <Separator />
      <span
        className={cn(
          "font-normal",
          twoSegment ? "text-foreground" : "text-foreground/70",
        )}
      >
        {formatted.operator}
      </span>
      {!twoSegment && (
        <>
          <Separator />
          <span className="text-foreground">{formatted.value}</span>
        </>
      )}
    </>
  );

  const removeButton = (
    <Button
      type="button"
      size="icon"
      variant="ghost"
      className="ml-1 rounded-full text-destructive/60 hover:text-destructive hover:shadow-none hover:bg-transparent"
      onClick={handleRemove}
      aria-label="Remove filter"
    >
      <XIcon className="h-3.5 w-3.5" aria-hidden={true} />
    </Button>
  );

  if (isReadOnly) {
    return (
      <Badge
        variant="outline"
        className="bg-background border-border text-foreground"
      >
        {segments}
        {removeButton}
      </Badge>
    );
  }

  return (
    <Popover open={open} onOpenChange={setOpen} modal={true}>
      <Badge
        variant="outline"
        className={cn(
          "bg-background border-border text-foreground",
          "hover:bg-accent hover:text-accent-foreground",
          "has-data-[state=open]:bg-accent has-data-[state=open]:text-accent-foreground",
          "transition-colors",
        )}
      >
        <PopoverTrigger asChild={true}>
          <button
            type="button"
            className="inline-flex items-center cursor-pointer bg-transparent border-0 p-0 [font:inherit] text-inherit"
            aria-label={`Edit filter on ${columnId}`}
          >
            {segments}
          </button>
        </PopoverTrigger>
        {removeButton}
      </Badge>
      <PopoverContent
        className="w-auto p-0"
        align="start"
        alignOffset={-10}
        sideOffset={10}
        avoidCollisions={true}
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <FilterPillEditor
          snapshot={{ columnId, value }}
          table={table}
          calculateTopKRows={calculateTopKRows}
          onClose={() => setOpen(false)}
        />
      </PopoverContent>
    </Popover>
  );
};

function Separator() {
  return (
    <span aria-hidden={true} className="mx-1.5 w-px h-3 bg-foreground/30" />
  );
}

interface FormattedFilter {
  operator: string;
  value?: string;
}

function formatValue(
  value: ColumnFilterValue,
  timeFormatter: DateFormatter,
): FormattedFilter | undefined {
  if (!("type" in value)) {
    return;
  }

  if (value.operator === "is_null") {
    return { operator: "is null" };
  }
  if (value.operator === "is_not_null") {
    return { operator: "is not null" };
  }

  if (value.type === "number") {
    return formatMinMax(value.min, value.max);
  }
  if (value.type === "date") {
    return formatMinMax(value.min?.toISOString(), value.max?.toISOString());
  }
  if (value.type === "time") {
    return formatMinMax(
      value.min ? timeFormatter.format(value.min) : undefined,
      value.max ? timeFormatter.format(value.max) : undefined,
    );
  }
  if (value.type === "datetime") {
    return formatMinMax(value.min?.toISOString(), value.max?.toISOString());
  }
  if (value.type === "boolean") {
    return { operator: `is ${value.value ? "True" : "False"}` };
  }
  if (value.type === "select") {
    const stringifiedOptions = value.options.map((o) =>
      stringifyUnknownValue({ value: o }),
    );
    return {
      operator: value.operator === "in" ? "is in" : "not in",
      value: `[${stringifiedOptions.join(", ")}]`,
    };
  }
  if (value.type === "text") {
    return { operator: "contains", value: `"${value.text}"` };
  }
  logNever(value);
  return undefined;
}

function formatMinMax(
  min: string | number | undefined,
  max: string | number | undefined,
): FormattedFilter | undefined {
  if (min === undefined && max === undefined) {
    return;
  }
  if (min === max) {
    return { operator: "==", value: String(min) };
  }
  if (min === undefined) {
    return { operator: "<=", value: String(max) };
  }
  if (max === undefined) {
    return { operator: ">=", value: String(min) };
  }
  return { operator: "between", value: `${min} - ${max}` };
}
