/* Copyright 2026 Marimo. All rights reserved. */
import * as React from "react";
import { ComboboxItem } from "../combobox";
import type { Option, OptionState } from "./types";

interface OptionRowProps<V> {
  option: Option<V>;
  checked: boolean;
  active: boolean;
  renderOption?: (option: Option<V>, state: OptionState) => React.ReactNode;
}

function OptionRowImpl<V>({
  option,
  checked,
  active,
  renderOption,
}: OptionRowProps<V>): React.JSX.Element {
  return (
    <ComboboxItem
      data-slot="select-option"
      data-checked={checked || undefined}
      value={option.label}
      disabled={option.disabled}
    >
      {renderOption ? renderOption(option, { checked, active }) : option.label}
    </ComboboxItem>
  );
}

export const OptionRow = React.memo(OptionRowImpl) as typeof OptionRowImpl;
