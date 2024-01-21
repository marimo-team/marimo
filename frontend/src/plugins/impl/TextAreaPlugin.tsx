/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { IPlugin, IPluginProps, Setter } from "../types";

import { Textarea } from "../../components/ui/textarea";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";

type T = string;

interface Data {
  placeholder: string;
  label: string | null;
  maxLength?: number;
  minLength?: number;
  disabled?: boolean;
  rows: number;
  fullWidth: boolean;
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
    rows: z.number().default(4),
    fullWidth: z.boolean().default(false),
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
    <Labeled label={props.label} align="top" fullWidth={props.fullWidth}>
      <Textarea
        className={cn("font-code", {
          "w-full": props.fullWidth,
        })}
        rows={props.rows}
        cols={33}
        maxLength={props.maxLength}
        minLength={props.minLength}
        required={props.minLength != null && props.minLength > 0}
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
