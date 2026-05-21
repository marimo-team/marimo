/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { ColumnFiltersState, Table } from "@tanstack/react-table";
import { MoreHorizontalIcon, XIcon } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { type DateFormatter, useDateFormatter } from "react-aria";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import { logNever } from "@/utils/assertNever";
import { cn } from "@/utils/cn";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { DraggablePopover } from "../ui/draggable-popover";
import {
  Popover,
  PopoverClose,
  PopoverContent,
  PopoverTrigger,
} from "../ui/popover";
import { Tooltip } from "../ui/tooltip";
import { AddFilterButton } from "./add-filter-button";
import { FilterPillEditor, type Snapshot } from "./filter-pill-editor";
import {
  type ColumnFilterValue,
  dateToISODate,
  dateToISODateTime,
} from "./filters";
import { OPERATOR_LABELS } from "./operator-labels";
import { stringifyUnknownValue } from "./utils";
import { ChipWithComma, CompactChipRow } from "./value-chips";

interface Props<TData> {
  filters: ColumnFiltersState | undefined;
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
  addFilterSnapshot: Snapshot | null;
  onAddFilterSnapshotChange: (snapshot: Snapshot | null) => void;
}

const useHasOverflow = (
  ref: React.RefObject<HTMLElement | null>,
  signature: string,
): boolean => {
  const [hasOverflow, setHasOverflow] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }
    const measure = () => setHasOverflow(el.scrollWidth > el.clientWidth);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
    // biome-ignore lint/correctness/useExhaustiveDependencies: signature triggers re-measure on filter content change
  }, [ref, signature]);
  return hasOverflow;
};

export const FilterPills = <TData,>({
  filters,
  table,
  calculateTopKRows,
  addFilterSnapshot,
  onAddFilterSnapshotChange,
}: Props<TData>) => {
  const timeFormatter = useDateFormatter({
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  const containerRef = useRef<HTMLDivElement | null>(null);
  const [overflowOpen, setOverflowOpen] = useState(false);
  const allFilters = filters ?? [];
  const signature = allFilters
    .map((f) => `${f.id}:${JSON.stringify(f.value)}`)
    .join("|");
  const hasOverflow = useHasOverflow(containerRef, signature);

  if (allFilters.length === 0 && addFilterSnapshot === null) {
    return null;
  }

  const renderPill = (filter: ColumnFiltersState[number], index: number) => (
    <FilterPill
      key={`${filter.id}:${index}`}
      columnId={filter.id}
      value={filter.value as ColumnFilterValue}
      index={index}
      timeFormatter={timeFormatter}
      table={table}
      calculateTopKRows={calculateTopKRows}
      onRemove={() =>
        table.setColumnFilters((current) =>
          current.filter((_, i) => i !== index),
        )
      }
    />
  );

  return (
    <div
      part="filter-pills"
      className="relative flex items-center gap-2 px-1 py-2"
    >
      <AddFilterButton
        table={table}
        calculateTopKRows={calculateTopKRows}
        snapshot={addFilterSnapshot}
        onSnapshotChange={onAddFilterSnapshotChange}
      />
      <div
        ref={containerRef}
        className={cn(
          "flex flex-nowrap items-center gap-2 overflow-hidden min-w-0 flex-1",
          hasOverflow &&
            "mask-[linear-gradient(to_right,black_calc(100%-2rem),transparent)]",
        )}
      >
        {allFilters.map((filter, index) => renderPill(filter, index))}
      </div>
      {hasOverflow && (
        <button
          type="button"
          onClick={() => setOverflowOpen(true)}
          className="shrink-0 inline-flex items-center gap-0.5 rounded-full border border-border bg-background px-2 py-0.5 text-xs text-foreground hover:bg-accent hover:text-accent-foreground"
          aria-label="See all filters"
        >
          <MoreHorizontalIcon className="h-3.5 w-3.5" aria-hidden={true} />
          <span>See all</span>
        </button>
      )}
      {hasOverflow && (
        <DraggablePopover
          open={overflowOpen}
          onOpenChange={setOverflowOpen}
          className="w-fit max-w-[min(90vw,40rem)] p-0"
        >
          <PopoverClose className="absolute top-2 right-2">
            <XIcon className="h-4 w-4" aria-hidden={true} />
          </PopoverClose>
          <div className="flex flex-col pt-7">
            <div className="max-h-80 overflow-y-auto flex flex-col items-start gap-2 px-3 pb-2">
              {allFilters.map((filter, index) => renderPill(filter, index))}
            </div>
            <div className="flex justify-end border-t border-border px-3 py-2">
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => {
                  table.setColumnFilters([]);
                  setOverflowOpen(false);
                }}
              >
                Clear all
              </Button>
            </div>
          </div>
        </DraggablePopover>
      )}
    </div>
  );
};

interface FilterPillProps<TData> {
  columnId: string;
  value: ColumnFilterValue;
  index: number;
  timeFormatter: DateFormatter;
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
  onRemove: () => void;
}

const FilterPill = <TData,>({
  columnId,
  value,
  index,
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

  const twoSegment =
    formatted.kind === "scalar" && formatted.value === undefined;

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRemove();
  };

  const renderValue = (truncateValue: boolean) => {
    if (formatted.kind === "scalar") {
      return (
        <span
          className={cn(
            "font-semibold text-foreground",
            truncateValue &&
              "inline-block max-w-[24ch] overflow-hidden text-ellipsis whitespace-nowrap align-middle",
          )}
        >
          {formatted.value}
        </span>
      );
    }
    if (truncateValue) {
      return <CompactChipRow items={formatted.items} max={3} />;
    }
    return (
      <span className="grid grid-cols-[repeat(5,max-content)] gap-1">
        {formatted.items.map((item, i) => (
          <ChipWithComma
            key={i}
            value={item}
            showComma={i < formatted.items.length - 1}
          />
        ))}
      </span>
    );
  };

  const renderSegments = (truncateValue: boolean) => (
    <>
      <span className="font-semibold text-foreground">{columnId}</span>
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
          {renderValue(truncateValue)}
        </>
      )}
    </>
  );

  const tooltip = (
    <span className="inline-flex items-center">{renderSegments(false)}</span>
  );
  const segments = renderSegments(true);

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

  return (
    <Popover open={open} onOpenChange={setOpen} modal={false}>
      <Badge
        variant="outline"
        className={cn(
          "bg-background border-border text-foreground",
          "hover:bg-accent hover:text-accent-foreground",
          "has-data-[state=open]:bg-accent has-data-[state=open]:text-accent-foreground",
          "transition-colors",
        )}
      >
        <Tooltip content={tooltip}>
          <span className="inline-flex items-center">
            <PopoverTrigger asChild={true}>
              <button
                type="button"
                className="inline-flex items-center whitespace-nowrap cursor-pointer bg-transparent border-0 p-0 [font:inherit] text-inherit"
                aria-label={`Edit filter on ${columnId}`}
              >
                {segments}
              </button>
            </PopoverTrigger>
            {removeButton}
          </span>
        </Tooltip>
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
          editIndex={index}
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

type FormattedFilter =
  | { kind: "scalar"; operator: string; value?: string }
  | { kind: "list"; operator: string; items: string[] };

function formatValue(
  value: ColumnFilterValue,
  timeFormatter: DateFormatter,
): FormattedFilter | undefined {
  if (!("type" in value)) {
    return;
  }

  if (value.operator === "is_null") {
    return { kind: "scalar", operator: "is null" };
  }
  if (value.operator === "is_not_null") {
    return { kind: "scalar", operator: "is not null" };
  }

  if (value.type === "number") {
    switch (value.operator) {
      case "between":
        return {
          kind: "scalar",
          operator: OPERATOR_LABELS.between.toLowerCase(),
          value: `${value.min} - ${value.max}`,
        };
      case "==":
      case "!=":
      case ">":
      case ">=":
      case "<":
      case "<=":
        return {
          kind: "scalar",
          operator: value.operator,
          value: String(value.value),
        };
    }
  }
  if (value.type === "text") {
    switch (value.operator) {
      case "in":
      case "not_in":
        return {
          kind: "list",
          operator: value.operator === "in" ? "is in" : "not in",
          items: [...value.values].toSorted((a, b) => a.localeCompare(b)),
        };
      case "is_empty":
        return { kind: "scalar", operator: "is empty" };
      case "contains":
      case "equals":
      case "does_not_equal":
      case "regex":
      case "starts_with":
      case "ends_with":
        return {
          kind: "scalar",
          operator: OPERATOR_LABELS[value.operator].toLowerCase(),
          value: `"${value.text}"`,
        };
    }
  }
  if (
    value.type === "date" ||
    value.type === "datetime" ||
    value.type === "time"
  ) {
    const format =
      value.type === "time"
        ? (d: Date) => timeFormatter.format(d)
        : value.type === "date"
          ? dateToISODate
          : dateToISODateTime;
    switch (value.operator) {
      case "between":
        return {
          kind: "scalar",
          operator: OPERATOR_LABELS.between.toLowerCase(),
          value: `${format(value.min)} - ${format(value.max)}`,
        };
      case "==":
      case "!=":
      case ">":
      case ">=":
      case "<":
      case "<=":
        return {
          kind: "scalar",
          operator: value.operator,
          value: format(value.value),
        };
    }
  }
  if (value.type === "boolean") {
    return {
      kind: "scalar",
      operator: `is ${value.value ? "True" : "False"}`,
    };
  }
  if (value.type === "select") {
    return {
      kind: "list",
      operator: value.operator === "in" ? "is in" : "not in",
      items: value.options
        .map((o) => stringifyUnknownValue({ value: o }))
        .toSorted((a, b) => a.localeCompare(b)),
    };
  }
  logNever(value);
  return undefined;
}
