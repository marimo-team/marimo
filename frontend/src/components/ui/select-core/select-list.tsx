/* Copyright 2026 Marimo. All rights reserved. */
import type * as React from "react";
import { Virtuoso } from "react-virtuoso";
import { CompactChipRow } from "@/components/ui/value-chips";
import { cn } from "@/utils/cn";
import { Combobox } from "../combobox";
import { CommandItem, CommandSeparator } from "../command";
import { OptionRow } from "./option-row";
import { renderSlot, type Slot } from "./render-slot";
import type { BulkAction, Option, OptionState } from "./types";
import { useSelectList } from "./use-select-list";

/** Above this many options the list virtualizes. */
export const VIRTUALIZE_THRESHOLD = 200;

/** Fixed pixel height of the virtualized viewport (Virtuoso requires one). */
export const VIRTUALIZED_LIST_HEIGHT = 200;

function bulkActionLabel<V>(action: BulkAction<V>): string {
  switch (action.kind) {
    case "select-all":
      return "Select all";
    case "deselect-all":
      return "Deselect all";
    case "select-matching":
      return `Select ${action.items.length} matching`;
    case "deselect-matching":
      return `Deselect ${action.items.length} matching`;
  }
}

interface SelectListProps<V> {
  options: Array<Option<V>>;
  /** Current selection: an array when `multiple`, otherwise a single value or null. */
  value: V[] | V | null;
  onChange: (next: V[] | V | null) => void;
  /** Multi-select when true; single-select (replace-on-pick) when false. */
  multiple: boolean;
  /** Cap on multi-select size. At the cap, picking another drops the oldest. */
  maxSelections?: number;
  /** Single-select only: re-picking the current value clears it to null. */
  allowSelectNone?: boolean;
  /** Float the (frozen) selection to the top of the idle menu, with a separator. */
  pinSelected?: boolean;
  /** Summarize the selection in the trigger as a compact chip row instead of "N selected". */
  compactChipTrigger?: boolean;
  placeholder?: string;
  disabled?: boolean;
  fullWidth?: boolean;
  className?: string;
  id?: string;
  "data-testid"?: string;
  /** Renders the row content; the core owns the interactive container. */
  renderOption?: (option: Option<V>, state: OptionState) => React.ReactNode;
  /** Shown when no option matches the current query. */
  renderEmpty?: Slot;
  /**
   * Virtualize once the visible option count exceeds this. Lower it when
   * `renderOption` produces expensive rows so they virtualize sooner.
   */
  virtualizeThreshold?: number;
  /** Fixed pixel height of the virtualized viewport. */
  virtualizedHeight?: number;
}

export function SelectList<V>(props: SelectListProps<V>): React.JSX.Element {
  const {
    options,
    value,
    onChange,
    multiple,
    maxSelections,
    allowSelectNone,
    pinSelected = false,
    compactChipTrigger = false,
    placeholder = "Select...",
    disabled = false,
    fullWidth = false,
    className,
    id,
    renderOption,
    renderEmpty = "Nothing found.",
    virtualizeThreshold = VIRTUALIZE_THRESHOLD,
    virtualizedHeight = VIRTUALIZED_LIST_HEIGHT,
  } = props;

  const list = useSelectList<V>({
    options,
    value,
    onChange,
    multiple,
    maxSelections,
    allowSelectNone,
    pinSelected,
  });

  const handleComboChange = (next: V[] | V | null): void => {
    if (!multiple) {
      if (next == null && !allowSelectNone) {
        return;
      }
      onChange(next);
      return;
    }
    let arr = Array.isArray(next) ? next : [];
    if (maxSelections != null && arr.length > maxSelections) {
      arr = arr.slice(-maxSelections);
    }
    onChange(arr);
  };

  // Bulk rows render as raw CommandItem (not ComboboxItem) so Combobox's per-item
  // toggle doesn't intercept them — only the action's own `run` fires on select.
  const bulkRows: React.ReactNode[] = list.bulkActions.map((action) => {
    const disabled =
      "enabled" in action ? !action.enabled : action.items.length === 0;
    return (
      <CommandItem
        key={action.kind}
        data-slot="select-bulk"
        className="pl-6 m-1 py-1"
        value={`__bulk_${action.kind}`}
        disabled={disabled}
        onSelect={() => {
          if (!disabled) {
            action.run();
          }
        }}
      >
        {bulkActionLabel(action)}
      </CommandItem>
    );
  });
  if (bulkRows.length > 0) {
    bulkRows.push(
      <CommandSeparator key="_bulk_separator" data-slot="select-separator" />,
    );
  }

  // Rendered at the start of the first unpinned row, not after the last pinned row,
  // so the menu-separator's `last:hidden` Tailwind variant doesn't hide it inside
  // Virtuoso's per-item wrapper.
  const pinnedSeparator = (index: number): React.ReactNode =>
    list.pinnedCount > 0 &&
    index === list.pinnedCount &&
    list.pinnedCount < list.visibleOptions.length ? (
      <CommandSeparator key="_pinned_separator" data-slot="select-separator" />
    ) : null;

  const renderItems = () => {
    if (list.visibleOptions.length > virtualizeThreshold) {
      return (
        <Virtuoso
          data-slot="select-list"
          style={{ height: virtualizedHeight }}
          totalCount={list.visibleOptions.length}
          overscan={50}
          itemContent={(i: number) => {
            const option = list.visibleOptions[i];
            return (
              <>
                {i === 0 && bulkRows}
                {pinnedSeparator(i)}
                <OptionRow
                  option={option}
                  checked={list.isChecked(option.value)}
                  renderOption={renderOption}
                />
              </>
            );
          }}
        />
      );
    }

    const rows = list.visibleOptions.flatMap((option, i) => {
      const separator = pinnedSeparator(i);
      const row = (
        <OptionRow
          key={String(option.value)}
          option={option}
          checked={list.isChecked(option.value)}
          renderOption={renderOption}
        />
      );
      return separator ? [separator, row] : [row];
    });

    return (
      <>
        {bulkRows}
        {rows}
      </>
    );
  };

  const renderTriggerValue = (current: V[] | V | null): React.ReactNode => {
    const items = Array.isArray(current)
      ? current
      : current != null
        ? [current]
        : [];
    if (items.length === 0) {
      return <span className="text-muted-foreground">{placeholder}</span>;
    }
    return <CompactChipRow items={items.map(list.labelOf)} max={3} />;
  };

  // Props shared by both branches. `multiple`/`value`/`onValueChange` are the
  // Combobox's discriminant trio, so they're set per-branch below with the
  // literal `multiple` that matches each value/handler shape.
  const comboboxProps = {
    "data-slot": "select-root",
    "data-testid": props["data-testid"],
    displayValue: (option: V) => list.labelOf(option),
    renderValue: compactChipTrigger ? renderTriggerValue : undefined,
    placeholder,
    className: cn({ "w-full": fullWidth }, className),
    shouldFilter: false as const,
    search: list.searchQuery,
    onSearchChange: list.setSearchQuery,
    open: list.open,
    onOpenChange: list.setOpen,
    emptyState: renderSlot(renderEmpty),
    disabled,
    id,
  };

  return multiple ? (
    <Combobox<V>
      {...comboboxProps}
      multiple={true}
      value={value as V[] | null}
      onValueChange={handleComboChange}
    >
      {renderItems()}
    </Combobox>
  ) : (
    <Combobox<V>
      {...comboboxProps}
      multiple={false}
      value={value as V | null}
      onValueChange={handleComboChange}
    >
      {renderItems()}
    </Combobox>
  );
}
