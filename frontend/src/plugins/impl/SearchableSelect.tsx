/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useId, useMemo } from "react";
import type { Option } from "@/components/ui/select-core";
import { SelectList } from "@/components/ui/select-core";
import { cn } from "../../utils/cn";
import { Labeled } from "./common/labeled";

interface SearchableSelectProps {
  options: string[];
  value: string | null;
  setValue: (value: string | null) => void;
  label: string | null;
  allowSelectNone: boolean;
  fullWidth: boolean;
  disabled: boolean;
}

export const SearchableSelect = (props: SearchableSelectProps): JSX.Element => {
  const {
    options,
    value,
    setValue,
    label,
    allowSelectNone,
    fullWidth,
    disabled,
  } = props;
  const id = useId();

  const items = useMemo<Array<Option<string>>>(
    () => options.map((option) => ({ value: option, label: option })),
    [options],
  );

  return (
    <Labeled label={label} id={id} fullWidth={fullWidth}>
      <SelectList<string>
        id={id}
        options={items}
        value={value}
        onChange={(next) => setValue((next as string | null) ?? null)}
        multiple={false}
        allowSelectNone={allowSelectNone}
        fullWidth={fullWidth}
        disabled={disabled}
        className={cn({ "w-full": fullWidth })}
        data-testid="marimo-plugin-searchable-dropdown"
      />
    </Labeled>
  );
};
