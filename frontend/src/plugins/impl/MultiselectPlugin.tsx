/* Copyright 2023 Marimo. All rights reserved. */
import { useId } from "react";
import { Label } from "../../components/ui/label";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { HtmlOutput } from "../../editor/output/HtmlOutput";
import * as labelStyles from "./Label.styles";
import { Combobox, ComboboxItem } from "../../components/ui/combobox";

interface Data {
  label: string | null;
  options: string[];
}

type T = string[];

export class MultiselectPlugin implements IPlugin<T, Data> {
  tagName = "marimo-multiselect";

  validator = z.object({
    initialValue: z.array(z.string()),
    label: z.string().nullable(),
    options: z.array(z.string()),
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
  const labelElement =
    props.label === null ? null : (
      <Label htmlFor={id}>
        <HtmlOutput html={props.label} inline={true} />
      </Label>
    );

  return (
    <div className={labelStyles.labelContainer}>
      {labelElement}
      <Combobox<string>
        displayValue={(option) => option}
        placeholder="Select..."
        multiple={true}
        value={props.value}
        onValueChange={(newValues) => props.setValue(newValues || [])}
      >
        {props.options.map((option) => (
          <ComboboxItem key={option} value={option}>
            {option}
          </ComboboxItem>
        ))}
      </Combobox>
    </div>
  );
};
