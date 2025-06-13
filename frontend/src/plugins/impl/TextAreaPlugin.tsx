/* Copyright 2024 Marimo. All rights reserved. */

import type { JSX } from "react";
import { z } from "zod";
import { cn } from "@/utils/cn";
import {
  DebouncedTextarea,
  OnBlurredTextarea,
  Textarea,
} from "../../components/ui/textarea";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";

type T = string;

interface Data {
  placeholder: string;
  label: string | null;
  maxLength?: number;
  minLength?: number;
  disabled?: boolean;
  debounce?: boolean | number;
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
    debounce: z.optional(z.union([z.boolean(), z.number()])),
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

  if (props.debounce === true) {
    return (
      <Labeled label={props.label} align="top" fullWidth={props.fullWidth}>
        <OnBlurredTextarea
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
          onValueChange={props.setValue}
          placeholder={props.placeholder}
        />
      </Labeled>
    );
  }

  if (typeof props.debounce === "number") {
    return (
      <Labeled label={props.label} align="top" fullWidth={props.fullWidth}>
        <DebouncedTextarea
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
          onValueChange={props.setValue}
          placeholder={props.placeholder}
          delay={props.debounce}
        />
      </Labeled>
    );
  }

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
