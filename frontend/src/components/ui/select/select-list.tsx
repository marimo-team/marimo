/* Copyright 2026 Marimo. All rights reserved. */
import type * as React from "react";
import { Virtuoso } from "react-virtuoso";
import { cn } from "@/utils/cn";
import { Combobox } from "../combobox";
import { OptionRow } from "./option-row";
import { renderSlot, type Slot } from "./render-slot";
import type { Option, OptionState } from "./types";
import { useSelectList } from "./use-select-list";

/** Above this many options the list virtualizes. */
export const VIRTUALIZE_THRESHOLD = 200;

/** Fixed pixel height of the virtualized viewport (Virtuoso requires one). */
export const VIRTUALIZED_LIST_HEIGHT = 200;

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
  chips?: boolean;
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
    chips = false,
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
  });

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
              <OptionRow
                option={option}
                checked={list.isChecked(option.value)}
                active={false}
                renderOption={renderOption}
              />
            );
          }}
        />
      );
    }

    return list.visibleOptions.map((option) => (
      <OptionRow
        key={String(option.value)}
        option={option}
        checked={list.isChecked(option.value)}
        active={false}
        renderOption={renderOption}
      />
    ));
  };

  return (
    <Combobox<V>
      data-slot="select-root"
      displayValue={(option) => {
        const match = options.find((o) => o.value === option);
        return match ? match.label : String(option);
      }}
      placeholder={placeholder}
      multiple={multiple as true}
      chips={chips}
      className={cn({ "w-full": fullWidth }, className)}
      value={value as V[]}
      onValueChange={(next: V[] | null) => onChange(next)}
      shouldFilter={false}
      search={list.searchQuery}
      onSearchChange={list.setSearchQuery}
      open={list.open}
      onOpenChange={list.setOpen}
      emptyState={renderSlot(renderEmpty)}
      disabled={disabled}
      id={id}
      data-testid={props["data-testid"]}
    >
      {renderItems()}
    </Combobox>
  );
}
