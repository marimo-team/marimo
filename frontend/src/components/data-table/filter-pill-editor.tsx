/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column, Table } from "@tanstack/react-table";
import { CheckIcon, MinusIcon, Trash2Icon, XIcon } from "lucide-react";
import { useId, useState } from "react";
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
import {
  FilterByValuesList,
  FilterByValuesPicker,
} from "./filter-by-values-picker";
import {
  type ColumnFilterValue,
  Filter,
  MEMBERSHIP_OPS,
  NUMBER_COMPARISON_OPS,
  type NumberComparisonOp,
  NUMBER_OPS,
  TEXT_OPS,
  TEXT_SCALAR_OPS,
  type TextScalarOp,
} from "./filters";
import { OPERATOR_LABELS } from "./operator-labels";
import { Tooltip } from "../ui/tooltip";

type EditableFilterType = "number" | "text" | "boolean" | "select";

const BOOLEAN_OPS = ["is_true", "is_false", "is_null", "is_not_null"] as const;
const SELECT_OPS = MEMBERSHIP_OPS;

const OPERATORS_BY_TYPE: Record<
  EditableFilterType,
  ReadonlyArray<OperatorType>
> = {
  number: NUMBER_OPS,
  text: TEXT_OPS,
  boolean: BOOLEAN_OPS,
  select: SELECT_OPS,
};

const DEFAULT_OPERATOR: Record<EditableFilterType, OperatorType> = {
  number: "between",
  text: "contains",
  boolean: "is_true",
  select: "in",
};

const OPERATORS_WITHOUT_VALUE = new Set<OperatorType>([
  "is_true",
  "is_false",
  "is_null",
  "is_not_null",
  "is_empty",
]);

const NUMBER_COMPARISON_SET: ReadonlySet<OperatorType> = new Set(
  NUMBER_COMPARISON_OPS,
);
const TEXT_SCALAR_SET: ReadonlySet<OperatorType> = new Set(TEXT_SCALAR_OPS);

const isNumberComparisonOp = (op: OperatorType): op is NumberComparisonOp =>
  NUMBER_COMPARISON_SET.has(op);
const isTextScalarOp = (op: OperatorType): op is TextScalarOp =>
  TEXT_SCALAR_SET.has(op);

type DraftValue =
  | { kind: "between"; min?: number; max?: number }
  | { kind: "single-number"; value?: number }
  | { kind: "single-text"; text?: string }
  | { kind: "multi-text"; values?: string[] }
  | { kind: "options"; options?: unknown[] }
  | { kind: "none" };

interface Snapshot {
  columnId: string;
  value: ColumnFilterValue;
}

interface FilterPillEditorProps<TData> {
  snapshot: Snapshot;
  table: Table<TData>;
  calculateTopKRows?: CalculateTopKRows;
  onClose: () => void;
}

export const FilterPillEditor = <TData,>({
  snapshot,
  table,
  calculateTopKRows,
  onClose,
}: FilterPillEditorProps<TData>) => {
  const columnId = useId();
  const operatorId = useId();
  const valueId = useId();

  const snapshotType = getEditableType(snapshot.value);
  const snapshotOperator = snapshot.value.operator as OperatorType;
  const snapshotDraft = toDraftValue(snapshot.value);

  const [draftColumnId, setDraftColumnId] = useState<string>(snapshot.columnId);
  const [draftType, setDraftType] = useState<EditableFilterType>(snapshotType);
  const [draftOperator, setDraftOperator] =
    useState<OperatorType>(snapshotOperator);
  const [draftValue, setDraftValue] = useState<DraftValue>(snapshotDraft);

  const editableColumns = table.getAllColumns().filter((c) => {
    const ft = c.columnDef.meta?.filterType;
    return (
      ft === "number" || ft === "text" || ft === "boolean" || ft === "select"
    );
  });

  const rehydrateIfMatchesSnapshot = (args: {
    id: string;
    operator: OperatorType;
  }) => {
    if (
      args.id === snapshot.columnId &&
      args.operator === snapshotOperator
    ) {
      setDraftValue(snapshotDraft);
    }
  };

  const handleColumnChange = (nextColumnId: string | null) => {
    if (!nextColumnId) {
      return;
    }
    const nextColumn = table.getColumn(nextColumnId);
    const nextColumnType = (nextColumn?.columnDef.meta?.filterType ??
      "text") as EditableFilterType;

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
    setDraftValue(emptyDraftFor(draftType, nextOp));
    rehydrateIfMatchesSnapshot({
      id: draftColumnId,
      operator: nextOp,
    });
  };

  const handleApply = () => {
    const value = buildFilterValue({
      type: draftType,
      operator: draftOperator,
      draft: draftValue,
    });
    if (!value) {
      return;
    }
    table.setColumnFilters((filters) => {
      const dropIds = new Set([snapshot.columnId, draftColumnId]);
      const filtered = filters.filter((f) => !dropIds.has(f.id));
      return [...filtered, { id: draftColumnId, value }];
    });
    onClose();
  };

  const handleClear = () => {
    table.setColumnFilters((filters) =>
      filters.filter((f) => f.id !== snapshot.columnId),
    );
    onClose();
  };

  const showValueSlot = !OPERATORS_WITHOUT_VALUE.has(draftOperator);
  const operatorOptions = OPERATORS_BY_TYPE[draftType];

  return (
    <div className="flex flex-row gap-4 items-end p-3">
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
          {editableColumns.map((c) => (
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
          value={draftOperator}
          onValueChange={(v) => handleOperatorChange(v as OperatorType)}
        >
          <SelectTrigger id={operatorId} className="h-6 mb-1 bg-transparent">
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
        <div className="flex flex-col gap-1">
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
        <Tooltip content="Apply filter">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className="rounded-full text-primary hover:text-primary hover:bg-primary/10"
            onClick={handleApply}
            aria-label="Apply filter"
          >
            <CheckIcon className="h-3.5 w-3.5" aria-hidden={true} />
          </Button>
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
    </div>
  );
};

interface ValueSlotProps<TData, TValue> {
  id?: string;
  type: EditableFilterType;
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
      <div className="flex gap-1 items-center w-48">
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
      value.kind === "single-number" ? value : { kind: "single-number" as const };
    return (
      <NumberField
        id={id}
        value={v.value}
        onChange={(n) => onChange({ kind: "single-number", value: n })}
        aria-label="value"
        placeholder="value"
        className="border-input min-w-0"
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
      <div className="w-48">
        <FilterByValuesList
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={new Set(v.values ?? [])}
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
    return (
      <Input
        id={id}
        type="text"
        value={v.text ?? ""}
        onChange={(e) => onChange({ kind: "single-text", text: e.target.value })}
        placeholder="Text…"
        className="border-input min-w-0"
      />
    );
  }
  if (type === "select" && column) {
    const v = value.kind === "options" ? value : { kind: "options" as const };
    return (
      <div className="flex w-48">
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

function getEditableType(value: ColumnFilterValue): EditableFilterType {
  if (value.type === "number") {
    return "number";
  }
  if (value.type === "text") {
    return "text";
  }
  if (value.type === "boolean") {
    return "boolean";
  }
  if (value.type === "select") {
    return "select";
  }
  return "text";
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
  return { kind: "none" };
}

function emptyDraftFor(
  type: EditableFilterType,
  operator: OperatorType,
): DraftValue {
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
  return { kind: "none" };
}

function buildFilterValue({
  type,
  operator,
  draft,
}: {
  type: EditableFilterType;
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
  return undefined;
}
