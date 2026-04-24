/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Column, Table } from "@tanstack/react-table";
import { CheckIcon, MinusIcon, Trash2Icon, XIcon } from "lucide-react";
import { useId, useState } from "react";
import type { CalculateTopKRows } from "@/plugins/impl/DataTablePlugin";
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
import { FilterByValuesPicker } from "./filter-by-values-picker";
import { type ColumnFilterValue, Filter } from "./filters";
import { Tooltip } from "../ui/tooltip";

// Editable filter types in this editor — date/datetime/time are read-only
// Will add support for rest in next PR
type EditableFilterType = "number" | "text" | "boolean" | "select";

// UI-level operator for the operator dropdown. Today the committed filter
// value does not carry this operator for number ranges — ranges are
// converted to `>=` / `<=` condition pairs at the RPC boundary
// (`filterToFilterCondition`). The follow-up PR splits UI operators into
// distinct `<`, `>`, `between` variants and routes them through as-is.
type UiOperator =
  | "between"
  | "contains"
  | "is_true"
  | "is_false"
  | "is_null"
  | "is_not_null"
  | "in"
  | "not_in";

// will be expanded by a follow up PR
const OPERATORS_BY_TYPE: Record<EditableFilterType, UiOperator[]> = {
  number: ["between", "is_null", "is_not_null"],
  text: ["contains", "is_null", "is_not_null"],
  boolean: ["is_true", "is_false", "is_null", "is_not_null"],
  select: ["in", "not_in"],
};

const DEFAULT_OPERATOR: Record<EditableFilterType, UiOperator> = {
  number: "between",
  text: "contains",
  boolean: "is_true",
  select: "in",
};

const OPERATOR_LABELS: Record<UiOperator, string> = {
  between: "Between",
  contains: "Contains",
  is_true: "Is true",
  is_false: "Is false",
  is_null: "Is null",
  is_not_null: "Is not null",
  in: "Is in",
  not_in: "Not in",
};

const OPERATORS_WITHOUT_VALUE = new Set<UiOperator>([
  "is_true",
  "is_false",
  "is_null",
  "is_not_null",
]);

interface DraftValue {
  min?: number;
  max?: number;
  text?: string;
  options?: unknown[];
}

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
  snapshot, // current state of filter pre-edit
  table,
  calculateTopKRows,
  onClose,
}: FilterPillEditorProps<TData>) => {
  const columnId = useId();
  const operatorId = useId();
  const valueId = useId();

  const snapshotType = getEditableType(snapshot.value);
  const snapshotOperator = getUiOperator(snapshot.value);
  const snapshotDraft = toDraftValue(snapshot.value);

  const [draftColumnId, setDraftColumnId] = useState<string>(snapshot.columnId);
  const [draftType, setDraftType] = useState<EditableFilterType>(snapshotType);
  const [draftOperator, setDraftOperator] =
    useState<UiOperator>(snapshotOperator);
  const [draftValue, setDraftValue] = useState<DraftValue>(snapshotDraft);

  const editableColumns = table.getAllColumns().filter((c) => {
    const ft = c.columnDef.meta?.filterType;
    return (
      ft === "number" || ft === "text" || ft === "boolean" || ft === "select"
    );
  });

  // if we switch back to pre-edit column+operator
  // restore the original value as well
  const rehydrateIfMatchesSnapshot = (args: {
    id: string;
    type: EditableFilterType;
    operator: UiOperator;
  }) => {
    if (
      args.id === snapshot.columnId &&
      args.type === snapshotType &&
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
      setDraftValue({});
    }
    setDraftColumnId(nextColumnId);
    rehydrateIfMatchesSnapshot({
      id: nextColumnId,
      type: nextColumnType,
      operator: nextOperator,
    });
  };

  const handleOperatorChange = (nextOp: UiOperator) => {
    setDraftOperator(nextOp);
    rehydrateIfMatchesSnapshot({
      id: draftColumnId,
      type: draftType,
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
          onValueChange={(v) => handleOperatorChange(v as UiOperator)}
        >
          <SelectTrigger id={operatorId} className="h-6 mb-1 bg-transparent">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPERATORS_BY_TYPE[draftType].map((op) => (
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
  value: DraftValue;
  onChange: (next: DraftValue) => void;
  column: Column<TData, TValue> | null;
  calculateTopKRows?: CalculateTopKRows;
}

const ValueSlot = <TData, TValue>({
  id,
  type,
  value,
  onChange,
  column,
  calculateTopKRows,
}: ValueSlotProps<TData, TValue>) => {
  if (type === "number") {
    return (
      <div className="flex gap-1 items-center w-48">
        <NumberField
          id={id}
          value={value.min}
          onChange={(v) => onChange({ ...value, min: v })}
          aria-label="min"
          placeholder="min"
          className="border-input flex-1 min-w-0"
        />
        <MinusIcon className="h-5 w-5 text-muted-foreground shrink-0" />
        <NumberField
          value={value.max}
          onChange={(v) => onChange({ ...value, max: v })}
          aria-label="max"
          placeholder="max"
          className="border-input flex-1 min-w-0"
        />
      </div>
    );
  }
  if (type === "text") {
    return (
      <Input
        id={id}
        type="text"
        value={value.text ?? ""}
        onChange={(e) => onChange({ ...value, text: e.target.value })}
        placeholder="Text…"
        className="border-input min-w-0"
      />
    );
  }
  if (type === "select" && column) {
    return (
      <div className="flex w-48">
        <FilterByValuesPicker
          column={column}
          calculateTopKRows={calculateTopKRows}
          chosenValues={value.options ?? []}
          onChange={(values) => onChange({ ...value, options: values })}
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
  // date/datetime/time fall back to text; callers should guard. supported in future
  return "text";
}

function getUiOperator(value: ColumnFilterValue): UiOperator {
  if (value.operator === "is_null") {
    return "is_null";
  }
  if (value.operator === "is_not_null") {
    return "is_not_null";
  }
  if (value.type === "number") {
    return "between";
  }
  if (value.type === "text") {
    return "contains";
  }
  if (value.type === "boolean") {
    return value.value ? "is_true" : "is_false";
  }
  if (value.type === "select") {
    return value.operator === "not_in" ? "not_in" : "in";
  }
  return "contains";
}

function toDraftValue(value: ColumnFilterValue): DraftValue {
  if (value.type === "number") {
    return { min: value.min, max: value.max };
  }
  if (value.type === "text") {
    return { text: value.text };
  }
  if (value.type === "select") {
    return { options: [...value.options] };
  }
  return {};
}

function buildFilterValue({
  type,
  operator,
  draft,
}: {
  type: EditableFilterType;
  operator: UiOperator;
  draft: DraftValue;
}): ColumnFilterValue | undefined {
  if (operator === "is_null" || operator === "is_not_null") {
    const op = operator;
    if (type === "number") {
      return Filter.number({ operator: op });
    }
    if (type === "boolean") {
      return Filter.boolean({ operator: op });
    }
    return Filter.text({ operator: op });
  }
  if (type === "number") {
    if (draft.min === undefined && draft.max === undefined) {
      return undefined;
    }
    return Filter.number({ min: draft.min, max: draft.max });
  }
  if (type === "text") {
    if (!draft.text) {
      return undefined;
    }
    return Filter.text({
      text: draft.text,
      operator: "contains",
    });
  }
  if (type === "boolean") {
    if (operator === "is_true") {
      return Filter.boolean({
        value: true,
        operator: "is_true",
      });
    }
    if (operator === "is_false") {
      return Filter.boolean({
        value: false,
        operator: "is_false",
      });
    }
    return undefined;
  }
  if (type === "select") {
    if (!draft.options || draft.options.length === 0) {
      return undefined;
    }
    return Filter.select({
      options: draft.options,
      operator: operator === "not_in" ? "not_in" : "in",
    });
  }
  return undefined;
}
