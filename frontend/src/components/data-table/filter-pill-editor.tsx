/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column, Table } from "@tanstack/react-table";
import { CheckIcon, MinusIcon, Trash2Icon, XIcon } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
import type { OperatorType } from "@/plugins/impl/data-frames/utils/operators";
import { Combobox, ComboboxItem } from "../ui/combobox";
import { Input } from "../ui/input";
import { NumberField } from "../ui/number-field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import { Button } from "../ui/button";
import { DateLikeInput, DateLikeRangeInput } from "./date-filter-inputs";
import { FilterByValuesPicker } from "./filter-by-values-picker";
import { RegexInput } from "./regex-input";
import {
  type ColumnFilterValue,
  DATETIME_OPS,
  EDITABLE_FILTER_TYPES,
  Filter,
  type FilterType,
  isDatetimeComparisonOp,
  isNumberComparisonOp,
  isTextScalarOp,
  MEMBERSHIP_OPS,
  NUMBER_OPS,
  TEXT_OPS,
} from "./filters";
import { OPERATOR_LABELS } from "./operator-labels";
import { Tooltip } from "../ui/tooltip";

type DateLikeFilterType = Extract<FilterType, "date" | "datetime" | "time">;

const DATE_LIKE_TYPES: ReadonlySet<FilterType> = new Set([
  "date",
  "datetime",
  "time",
]);

const isDateLikeType = (type: FilterType): type is DateLikeFilterType =>
  DATE_LIKE_TYPES.has(type);

const BOOLEAN_OPS = ["is_true", "is_false", "is_null", "is_not_null"] as const;
const SELECT_OPS = MEMBERSHIP_OPS;

const OPERATORS_BY_TYPE: Record<FilterType, ReadonlyArray<OperatorType>> = {
  number: NUMBER_OPS,
  text: TEXT_OPS,
  boolean: BOOLEAN_OPS,
  select: SELECT_OPS,
  date: DATETIME_OPS,
  datetime: DATETIME_OPS,
  time: DATETIME_OPS,
};

const DEFAULT_OPERATOR: Record<FilterType, OperatorType> = {
  number: "between",
  text: "contains",
  boolean: "is_true",
  select: "in",
  date: "between",
  datetime: "between",
  time: "between",
};

const OPERATORS_WITHOUT_VALUE = new Set<OperatorType>([
  "is_true",
  "is_false",
  "is_null",
  "is_not_null",
  "is_empty",
]);

type DraftValue =
  | { kind: "between"; min?: number; max?: number }
  | { kind: "single-number"; value?: number }
  | { kind: "single-text"; text?: string }
  | { kind: "multi-text"; values?: string[] }
  | { kind: "options"; options?: unknown[] }
  | { kind: "date-between"; min?: Date; max?: Date }
  | { kind: "date-single"; value?: Date }
  | { kind: "none" };

export interface Snapshot {
  columnId: string;
  value: ColumnFilterValue;
}

function columnEditableType(column: Column<unknown, unknown>): FilterType {
  const ft = column.columnDef.meta?.filterType;
  return ft && EDITABLE_FILTER_TYPES.has(ft) ? (ft as FilterType) : "text";
}

/** Minimal ColumnFilterValue for a (type, operator) pair, seeding extra fields for shapes that require them. */
export function defaultFilterValueFor(
  type: FilterType,
  operator: OperatorType,
): ColumnFilterValue {
  if (type === "select") {
    return { type: "select", operator, options: [] } as ColumnFilterValue;
  }
  if (type === "text" && (operator === "in" || operator === "not_in")) {
    return { type: "text", operator, values: [] } as ColumnFilterValue;
  }
  return { type, operator } as ColumnFilterValue;
}

export function buildEmptyFilterValue(
  column: Column<unknown, unknown>,
): ColumnFilterValue {
  const type = columnEditableType(column);
  return defaultFilterValueFor(type, DEFAULT_OPERATOR[type]);
}

export function buildEditorSnapshot(
  column: Column<unknown, unknown>,
  opts?: { operator?: OperatorType },
): Snapshot {
  const columnType = columnEditableType(column);
  const isMembership = opts?.operator === "in" || opts?.operator === "not_in";
  const type = isMembership && columnType === "number" ? "select" : columnType;
  const operator = opts?.operator ?? DEFAULT_OPERATOR[type];
  return {
    columnId: column.id,
    value: defaultFilterValueFor(type, operator),
  };
}

export function editableColumns<TData>(
  table: Table<TData>,
): Array<Column<TData, unknown>> {
  return table.getAllColumns().filter((c) => {
    const ft = c.columnDef.meta?.filterType;
    return ft !== undefined && EDITABLE_FILTER_TYPES.has(ft);
  });
}

interface FilterPillEditorProps<TData> {
  snapshot: Snapshot;
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
  onClose: () => void;
  editIndex?: number; // skip for creating new pill; when passed edits the pill at idx instead
}

export const FilterPillEditor = <TData,>({
  snapshot,
  table,
  calculateTopKRows,
  onClose,
  editIndex,
}: FilterPillEditorProps<TData>) => {
  const columnId = useId();
  const operatorId = useId();
  const valueId = useId();

  const snapshotType = getEditableType(snapshot.value);
  const snapshotOperator = snapshot.value.operator as OperatorType;
  const snapshotDraft = toDraftValue(snapshot.value);

  const [draftColumnId, setDraftColumnId] = useState<string>(snapshot.columnId);
  const [draftType, setDraftType] = useState<FilterType>(snapshotType);
  const [draftOperator, setDraftOperator] =
    useState<OperatorType>(snapshotOperator);
  const [draftValue, setDraftValue] = useState<DraftValue>(snapshotDraft);

  const columnOptions = editableColumns(table);

  const rehydrateIfMatchesSnapshot = (args: {
    id: string;
    operator: OperatorType;
  }) => {
    if (args.id === snapshot.columnId && args.operator === snapshotOperator) {
      setDraftValue(snapshotDraft);
    }
  };

  const handleColumnChange = (nextColumnId: string | null) => {
    if (!nextColumnId) {
      return;
    }
    const nextColumn = table.getColumn(nextColumnId);
    const nextColumnType = (nextColumn?.columnDef.meta?.filterType ??
      "text") as FilterType;

    let nextOperator = draftOperator;
    if (nextColumnType !== draftType) {
      nextOperator = DEFAULT_OPERATOR[nextColumnType];
      setDraftType(nextColumnType);
      setDraftOperator(nextOperator);
      setDraftValue(emptyDraftFor(nextColumnType, nextOperator));
    }
    setDraftColumnId(nextColumnId);
    rehydrateIfMatchesSnapshot({
      id: nextColumnId,
      operator: nextOperator,
    });
  };

  const handleOperatorChange = (nextOp: OperatorType) => {
    setDraftOperator(nextOp);
    const nextEmpty = emptyDraftFor(draftType, nextOp);
    if (nextEmpty.kind !== draftValue.kind) {
      setDraftValue(nextEmpty);
    }
    rehydrateIfMatchesSnapshot({
      id: draftColumnId,
      operator: nextOp,
    });
  };

  const pendingValue = buildFilterValue({
    type: draftType,
    operator: draftOperator,
    draft: draftValue,
  });
  const applyDisabled = pendingValue === undefined;
  const applyTooltip = applyDisabled
    ? getMissingValueMessage(draftType, draftOperator)
    : "Apply filter";

  const handleApply = () => {
    if (!pendingValue) {
      return;
    }
    const value = pendingValue;
    table.setColumnFilters((filters) => {
      // assume new filter pill is being created
      if (editIndex === undefined) {
        return [{ id: draftColumnId, value }, ...filters];
      }
      const next = [...filters];
      next[editIndex] = { id: draftColumnId, value };
      return next;
    });
    onClose();
  };

  const handleClear = () => {
    if (editIndex !== undefined) {
      table.setColumnFilters((filters) =>
        filters.filter((_, i) => i !== editIndex),
      );
    }
    onClose();
  };

  const showValueSlot = !OPERATORS_WITHOUT_VALUE.has(draftOperator);
  const operatorOptions = OPERATORS_BY_TYPE[draftType];

  const valueSlotRef = useRef<HTMLDivElement>(null);
  const operatorTriggerRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const firstInput = valueSlotRef.current?.querySelector<HTMLElement>(
      'input, [role="spinbutton"], [role="combobox"], button',
    );
    if (firstInput) {
      firstInput.focus();
    } else {
      operatorTriggerRef.current?.focus();
    }
  }, [draftType, draftOperator]);

  return (
    <form
      className="flex flex-row gap-4 items-end p-3"
      onSubmit={(e) => {
        e.preventDefault();
        handleApply();
      }}
      onKeyDownCapture={(e) => {
        if (e.key === "Tab") {
          e.stopPropagation();
        }
      }}
    >
      <div className="flex flex-col gap-1">
        <label className="text-xs text-muted-foreground" htmlFor={columnId}>
          Column
        </label>
        <Combobox<string>
          id={columnId}
          value={draftColumnId}
          onValueChange={handleColumnChange}
          multiple={false}
          placeholder="Select column…"
          displayValue={(id) => id}
        >
          {columnOptions.map((c) => (
            <ComboboxItem key={c.id} value={c.id}>
              {c.id}
            </ComboboxItem>
          ))}
        </Combobox>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={operatorId} className="text-xs text-muted-foreground">
          Operator
        </label>
        <Select
          key={draftType}
          value={draftOperator}
          onValueChange={(v) => handleOperatorChange(v as OperatorType)}
        >
          <SelectTrigger
            ref={operatorTriggerRef}
            id={operatorId}
            className="h-6 mb-1 bg-transparent"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {operatorOptions.map((op) => (
              <SelectItem key={op} value={op}>
                {OPERATOR_LABELS[op]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {showValueSlot && (
        <div ref={valueSlotRef} className="flex flex-col gap-1">
          <label htmlFor={valueId} className="text-xs text-muted-foreground">
            Value
          </label>
          <ValueSlot
            id={valueId}
            type={draftType}
            operator={draftOperator}
            value={draftValue}
            onChange={setDraftValue}
            column={table.getColumn(draftColumnId) ?? null}
            calculateTopKRows={calculateTopKRows}
          />
        </div>
      )}
      <div className="flex gap-1 mb-1">
        <Tooltip content={applyTooltip}>
          <span className="inline-flex">
            <Button
              type="submit"
              size="icon"
              variant="ghost"
              disabled={applyDisabled}
              className="rounded-full text-primary hover:text-primary hover:bg-primary/10"
              aria-label="Apply filter"
            >
              <CheckIcon className="h-3.5 w-3.5" aria-hidden={true} />
            </Button>
          </span>
        </Tooltip>
        <Tooltip content="Close without saving">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="rounded-full text-muted-foreground hover:text-foreground hover:bg-muted"
            onClick={onClose}
            aria-label="Close without saving"
          >
            <XIcon className="h-3.5 w-3.5" aria-hidden={true} />
          </Button>
        </Tooltip>
        <Tooltip content="Remove filter">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="rounded-full text-destructive hover:text-destructive hover:bg-destructive/10"
            onClick={handleClear}
            aria-label="Remove filter"
          >
            <Trash2Icon className="h-3.5 w-3.5" aria-hidden={true} />
          </Button>
        </Tooltip>
      </div>
    </form>
  );
};

interface ValueSlotProps<TData, TValue> {
  id?: string;
  type: FilterType;
  operator: OperatorType;
  value: DraftValue;
  onChange: (next: DraftValue) => void;
  column: Column<TData, TValue> | null;
  calculateTopKRows?: CalculateTopKRows;
}

const ValueSlot = <TData, TValue>({
  id,
  type,
  operator,
  value,
  onChange,
  column,
  calculateTopKRows,
}: ValueSlotProps<TData, TValue>) => {
  if (type === "number" && operator === "between") {
    const v = value.kind === "between" ? value : { kind: "between" as const };
    return (
      <div className="flex gap-1 items-center w-44">
        <NumberField
          id={id}
          value={v.min}
          onChange={(n) => onChange({ kind: "between", min: n, max: v.max })}
          aria-label="min"
          placeholder="min"
          className="border-input flex-1 min-w-0"
        />
        <MinusIcon className="h-5 w-5 text-muted-foreground shrink-0" />
        <NumberField
          value={v.max}
          onChange={(n) => onChange({ kind: "between", min: v.min, max: n })}
          aria-label="max"
          placeholder="max"
          className="border-input flex-1 min-w-0"
        />
      </div>
    );
  }
  if (type === "number" && isNumberComparisonOp(operator)) {
    const v =
      value.kind === "single-number"
        ? value
        : { kind: "single-number" as const };
    return (
      <NumberField
        id={id}
        value={v.value}
        onChange={(n) => onChange({ kind: "single-number", value: n })}
        aria-label="value"
        placeholder="value"
        className="border-input w-24 min-w-0"
      />
    );
  }
  if (
    type === "text" &&
    (operator === "in" || operator === "not_in") &&
    column
  ) {
    const v =
      value.kind === "multi-text" ? value : { kind: "multi-text" as const };
    return (
      <div className="min-w-[14rem] w-fit max-w-[24rem]">
        <FilterByValuesPicker
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={v.values ?? []}
          onChange={(next) =>
            onChange({ kind: "multi-text", values: next.map(String) })
          }
          creatable={true}
        />
      </div>
    );
  }
  if (type === "text" && isTextScalarOp(operator)) {
    const v =
      value.kind === "single-text" ? value : { kind: "single-text" as const };
    if (operator === "regex") {
      return (
        <RegexInput
          id={id}
          value={v.text ?? ""}
          onChange={(text) => onChange({ kind: "single-text", text })}
          className="w-40"
        />
      );
    }
    return (
      <Input
        id={id}
        type="text"
        value={v.text ?? ""}
        onChange={(e) =>
          onChange({ kind: "single-text", text: e.target.value })
        }
        placeholder="Text…"
        className="border-input w-40 min-w-0"
      />
    );
  }
  if (isDateLikeType(type) && operator === "between") {
    const v =
      value.kind === "date-between" ? value : { kind: "date-between" as const };
    return (
      <DateLikeRangeInput
        key={`${column?.id ?? "_"}-${operator}`}
        filterType={type}
        min={v.min}
        max={v.max}
        onRangeChange={(min, max) =>
          onChange({ kind: "date-between", min, max })
        }
        className="border-input"
      />
    );
  }
  if (isDateLikeType(type) && isDatetimeComparisonOp(operator)) {
    const v =
      value.kind === "date-single" ? value : { kind: "date-single" as const };
    return (
      <DateLikeInput
        key={`${column?.id ?? "_"}-${operator}`}
        filterType={type}
        value={v.value}
        onChange={(next) => onChange({ kind: "date-single", value: next })}
        aria-label="value"
        className="border-input"
      />
    );
  }
  if (type === "select" && column) {
    const v = value.kind === "options" ? value : { kind: "options" as const };
    return (
      <div className="flex min-w-[14rem] w-fit max-w-[24rem]">
        <FilterByValuesPicker
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={v.options ?? []}
          onChange={(values) => onChange({ kind: "options", options: values })}
        />
      </div>
    );
  }
  return null;
};

function getEditableType(value: ColumnFilterValue): FilterType {
  switch (value.type) {
    case "number":
    case "text":
    case "boolean":
    case "select":
    case "date":
    case "datetime":
    case "time":
      return value.type;
    default:
      return "text";
  }
}

function toDraftValue(value: ColumnFilterValue): DraftValue {
  if (value.type === "number") {
    switch (value.operator) {
      case "between":
        return { kind: "between", min: value.min, max: value.max };
      case "is_null":
      case "is_not_null":
        return { kind: "none" };
      default:
        return { kind: "single-number", value: value.value };
    }
  }
  if (value.type === "text") {
    switch (value.operator) {
      case "in":
      case "not_in":
        return { kind: "multi-text", values: [...value.values] };
      case "is_null":
      case "is_not_null":
      case "is_empty":
        return { kind: "none" };
      default:
        return { kind: "single-text", text: value.text };
    }
  }
  if (value.type === "select") {
    return { kind: "options", options: [...value.options] };
  }
  if (
    value.type === "date" ||
    value.type === "datetime" ||
    value.type === "time"
  ) {
    switch (value.operator) {
      case "between":
        return { kind: "date-between", min: value.min, max: value.max };
      case "is_null":
      case "is_not_null":
        return { kind: "none" };
      default:
        return { kind: "date-single", value: value.value };
    }
  }
  return { kind: "none" };
}

function emptyDraftFor(type: FilterType, operator: OperatorType): DraftValue {
  if (OPERATORS_WITHOUT_VALUE.has(operator)) {
    return { kind: "none" };
  }
  if (type === "number") {
    return operator === "between"
      ? { kind: "between" }
      : { kind: "single-number" };
  }
  if (type === "text") {
    return operator === "in" || operator === "not_in"
      ? { kind: "multi-text", values: [] }
      : { kind: "single-text" };
  }
  if (type === "select") {
    return { kind: "options", options: [] };
  }
  if (isDateLikeType(type)) {
    return operator === "between"
      ? { kind: "date-between" }
      : { kind: "date-single" };
  }
  return { kind: "none" };
}

function getMissingValueMessage(
  type: FilterType,
  operator: OperatorType,
): string {
  if (operator === "between") {
    return "Min and max are required";
  }
  if (type === "text" && (operator === "in" || operator === "not_in")) {
    return "Pick at least one value";
  }
  return "Value is required";
}

function buildFilterValue({
  type,
  operator,
  draft,
}: {
  type: FilterType;
  operator: OperatorType;
  draft: DraftValue;
}): ColumnFilterValue | undefined {
  if (type === "number") {
    if (operator === "is_null" || operator === "is_not_null") {
      return Filter.number({ operator });
    }
    if (operator === "between") {
      if (
        draft.kind !== "between" ||
        draft.min === undefined ||
        draft.max === undefined
      ) {
        return undefined;
      }
      return Filter.number({
        operator: "between",
        min: draft.min,
        max: draft.max,
      });
    }
    if (!isNumberComparisonOp(operator)) {
      return undefined;
    }
    if (draft.kind !== "single-number" || draft.value === undefined) {
      return undefined;
    }
    return Filter.number({ operator, value: draft.value });
  }
  if (type === "text") {
    if (
      operator === "is_null" ||
      operator === "is_not_null" ||
      operator === "is_empty"
    ) {
      return Filter.text({ operator });
    }
    if (operator === "in" || operator === "not_in") {
      if (
        draft.kind !== "multi-text" ||
        !draft.values ||
        draft.values.length === 0
      ) {
        return undefined;
      }
      return Filter.text({ operator, values: draft.values });
    }
    if (!isTextScalarOp(operator)) {
      return undefined;
    }
    if (draft.kind !== "single-text" || !draft.text) {
      return undefined;
    }
    return Filter.text({ operator, text: draft.text });
  }
  if (type === "boolean") {
    if (operator === "is_true") {
      return Filter.boolean({ value: true, operator: "is_true" });
    }
    if (operator === "is_false") {
      return Filter.boolean({ value: false, operator: "is_false" });
    }
    if (operator === "is_null" || operator === "is_not_null") {
      return Filter.boolean({ operator });
    }
    return undefined;
  }
  if (type === "select") {
    if (
      draft.kind !== "options" ||
      !draft.options ||
      draft.options.length === 0
    ) {
      return undefined;
    }
    return Filter.select({
      options: draft.options,
      operator: operator === "not_in" ? "not_in" : "in",
    });
  }
  if (isDateLikeType(type)) {
    const factory =
      type === "date"
        ? Filter.date
        : type === "datetime"
          ? Filter.datetime
          : Filter.time;
    if (operator === "is_null" || operator === "is_not_null") {
      return factory({ operator });
    }
    if (operator === "between") {
      if (
        draft.kind !== "date-between" ||
        draft.min === undefined ||
        draft.max === undefined
      ) {
        return undefined;
      }
      return factory({ operator: "between", min: draft.min, max: draft.max });
    }
    if (!isDatetimeComparisonOp(operator)) {
      return undefined;
    }
    if (draft.kind !== "date-single" || draft.value === undefined) {
      return undefined;
    }
    return factory({ operator, value: draft.value });
  }
  return undefined;
}
