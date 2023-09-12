/* Copyright 2023 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { Textarea } from "../../components/ui/textarea";
import { Labeled } from "./common/labeled";

type T = string;

interface Data {
  placeholder: string;
  label: string | null;
  maxLength?: number;
  minLength?: number;
  disabled?: boolean;
}

export class TextAreaPlugin implements IPlugin<T, Data> {
  tagName = "marimo-text-area";

  validator = z.object({
    initialValue: z.string(),
    placeholder: z.string(),
    label: z.string().nullable(),
    maxLength: z.number().optional(),
    minLength: z.number().optional(),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <TextAreaComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface TextAreaComponentProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const TextAreaComponent = (props: TextAreaComponentProps) => {
  const bottomAdornment = props.maxLength ? (
    <span className="text-muted-foreground text-xs font-medium">
      {props.value.length}/{props.maxLength}
    </span>
  ) : null;

  return (
    <Labeled label={props.label} align="top">
      <Textarea
        className="font-code"
        rows={5}
        cols={33}
        maxLength={props.maxLength}
        minLength={props.minLength}
        disabled={props.disabled}
        bottomAdornment={bottomAdornment}
        value={props.value}
        onInput={(event) =>
          props.setValue((event.target as HTMLInputElement).value)
        }
        placeholder={props.placeholder}
      />
    </Labeled>
  );
};
