/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import type {
  ColumnFilter,
  ColumnFiltersState,
  Table,
} from "@tanstack/react-table";
import { Badge } from "../ui/badge";
import type { ColumnFilterValue } from "./filters";
import { logNever } from "@/utils/assertNever";
import { XIcon } from "lucide-react";
import { renderUnknownValue } from "./renderers";

interface Props<TData> {
  filters: ColumnFiltersState | undefined;
  table: Table<TData>;
}

export const FilterPills = <TData,>({ filters, table }: Props<TData>) => {
  if (!filters || filters.length === 0) {
    return null;
  }

  function renderFilterPill(filter: ColumnFilter) {
    const formattedValue = formatValue(filter.value as ColumnFilterValue);
    if (!formattedValue) {
      return null;
    }

    return (
      <Badge key={filter.id} variant="secondary" className="dark:invert">
        {filter.id} {formattedValue}{" "}
        <span
          className="cursor-pointer opacity-60 hover:opacity-100 pl-1 py-[2px]"
          onClick={() => {
            table.setColumnFilters((filters) =>
              filters.filter((f) => f.id !== filter.id),
            );
          }}
        >
          <XIcon className="w-3.5 h-3.5" />
        </span>
      </Badge>
    );
  }

  return (
    <div className="flex flex-wrap gap-2 px-1">
      {filters.map(renderFilterPill)}
    </div>
  );
};

function formatValue(value: ColumnFilterValue) {
  if (!("type" in value)) {
    return;
  }
  if (value.type === "number") {
    return formatMinMax(value.min, value.max);
  }
  if (value.type === "date") {
    return formatMinMax(value.min?.toISOString(), value.max?.toISOString());
  }
  if (value.type === "time") {
    const formatTime = new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    return formatMinMax(
      value.min ? formatTime.format(value.min) : undefined,
      value.max ? formatTime.format(value.max) : undefined,
    );
  }
  if (value.type === "datetime") {
    return formatMinMax(value.min?.toISOString(), value.max?.toISOString());
  }
  if (value.type === "boolean") {
    return `is ${value.value ? "True" : "False"}`;
  }
  if (value.type === "select") {
    const stringifiedOptions = value.options.map((o) =>
      renderUnknownValue({ value: o }),
    );
    return `is in [${stringifiedOptions.join(", ")}]`;
  }
  if (value.type === "text") {
    return `contains "${value.text}"`;
  }
  logNever(value);
  return undefined;
}

function formatMinMax(
  min: string | number | undefined,
  max: string | number | undefined,
) {
  if (min === undefined && max === undefined) {
    return;
  }
  if (min === max) {
    return `== ${min}`;
  }
  if (min === undefined) {
    return `<= ${max}`;
  }
  if (max === undefined) {
    return `>= ${min}`;
  }
  return `${min} - ${max}`;
}
