/* Copyright 2026 Marimo. All rights reserved. */
import * as React from "react";
import { ComboboxItem } from "../combobox";
import type { Option, OptionState } from "./types";

interface OptionRowProps<V> {
  option: Option<V>;
  checked: boolean;
  renderOption?: (option: Option<V>, state: OptionState) => React.ReactNode;
}

function OptionRowImpl<V>({
  option,
  checked,
  renderOption,
}: OptionRowProps<V>): React.JSX.Element {
  return (
    <ComboboxItem
      data-slot="select-option"
      data-checked={checked || undefined}
      // Selection identity, not the display string: the Combobox tracks
      // `isSelected`/`onSelect` by this value and echoes it back through
      // `onValueChange`. The cast bridges the unconstrained option type to
      // ComboboxItem's stringifiable-value bound.
      value={option.value as string | number}
      disabled={option.disabled}
    >
      {renderOption ? renderOption(option, { checked }) : option.label}
    </ComboboxItem>
  );
}

export const OptionRow = React.memo(OptionRowImpl) as typeof OptionRowImpl;
