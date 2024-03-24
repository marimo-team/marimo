/* Copyright 2024 Marimo. All rights reserved. */
import { useId } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Combobox, ComboboxItem } from "../../components/ui/combobox";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";

interface Data {
  label: string | null;
  options: string[];
  fullWidth: boolean;
  maxSelections?: number | undefined;
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

const Multiselect = (props: MultiselectProps): JSX.Element => {
  const id = useId();

  function setValue(newValues: T) {
    if (props.maxSelections != null && newValues.length > props.maxSelections) {
      return;
    }
    props.setValue(newValues);
  }

  return (
    <Labeled label={props.label} id={id} fullWidth={props.fullWidth}>
      <Combobox<string>
        displayValue={(option) => option}
        placeholder="Select..."
        multiple={true}
        filterFn={multiselectFilterFn}
        className={cn({
          "w-full": props.fullWidth,
        })}
        value={props.value}
        onValueChange={(newValues) => setValue(newValues || [])}
      >
        {props.options.map((option) => (
          <ComboboxItem key={option} value={option}>
            {option}
          </ComboboxItem>
        ))}
      </Combobox>
    </Labeled>
  );
};

/**
 * We override the default filter function which focuses on sorting by relevance with a fuzzy-match,
 * instead of filtering out.
 * The default filter function is `command-score`.
 *
 * Our filter function only matches if all words in the value are present in the option.
 * This is more strict than the default, but more lenient than an exact match.
 *
 * Examples:
 * - "foo bar" matches "foo bar"
 * - "bar foo" matches "foo bar"
 * - "foob" does not matches "foo bar"
 */
function multiselectFilterFn(option: string, value: string): number {
  const words = value.split(/\s+/);
  const match = words.every((word) =>
    option.toLowerCase().includes(word.toLowerCase()),
  );
  return match ? 1 : 0;
}

export const exportedForTesting = {
  multiselectFilterFn,
};
