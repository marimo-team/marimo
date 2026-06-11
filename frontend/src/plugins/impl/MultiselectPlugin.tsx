/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useId, useMemo } from "react";
import { z } from "zod";
import type { Option } from "@/components/ui/select-core";
import { SelectList } from "@/components/ui/select-core";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";

interface Data {
  label: string | null;
  options: string[];
  fullWidth: boolean;
  maxSelections?: number | undefined;
  disabled: boolean;
}

type T = string[];

export class MultiselectPlugin implements IPlugin<T, Data> {
  tagName = "marimo-multiselect";

  validator = z.object({
    initialValue: z.array(z.string()),
    label: z.string().nullable(),
    options: z.array(z.string()),
    fullWidth: z.boolean().default(false),
    maxSelections: z.number().optional(),
    disabled: z.boolean().default(false),
  });

  render(props: IPluginProps<string[], Data>): JSX.Element {
    return (
      <Multiselect
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

/**
 * Arguments for a multi select
 *
 * @param options - text labels for each select option
 * @param label - an optional label for the select
 * @param value - an array of options that are selected
 * @param setValue - set multi select value
 */
interface MultiselectProps extends Data {
  value: T;
  setValue: Setter<T>;
}

export const Multiselect = ({
  options,
  label,
  value,
  setValue,
  fullWidth,
  maxSelections,
  disabled,
}: MultiselectProps): JSX.Element => {
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
        onChange={(next: string[] | string | null) =>
          setValue((next as string[] | null) ?? [])
        }
        multiple={true}
        maxSelections={maxSelections}
        pinSelected={true}
        compactChipTrigger={true}
        fullWidth={fullWidth}
        disabled={disabled}
      />
    </Labeled>
  );
};
