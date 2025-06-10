/* Copyright 2024 Marimo. All rights reserved. */
import { useId, type JSX } from "react";
import { z } from "zod";

import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";
import { useDebounceControlledState } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { NumberField } from "@/components/ui/number-field";

type T = number;

interface Data {
  start?: T | null;
  stop?: T | null;
  step?: T;
  label: string | null;
  debounce: boolean;
  fullWidth: boolean;
  disabled?: boolean;
}

export class NumberPlugin implements IPlugin<T | null, Data> {
  tagName = "marimo-number";

  validator = z.object({
    initialValue: z.number().nullish(),
    label: z.string().nullable(),
    start: z.number().nullish(),
    stop: z.number().nullish(),
    step: z.number().optional(),
    debounce: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T | null, Data>): JSX.Element {
    return (
      <NumberComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface NumberComponentProps extends Data {
  value: T | null;
  setValue: Setter<T | null>;
}

const NumberComponent = (props: NumberComponentProps): JSX.Element => {
  let id = useId();
  if (import.meta.env.VITEST) {
    id = "test-id";
  }

  // Create a debounced value of 200
  const { value, onChange } = useDebounceControlledState({
    initialValue: props.value,
    delay: 200,
    disabled: !props.debounce,
    onChange: (v) => {
      props.setValue(v);
    },
  });

  return (
    <Labeled label={props.label} id={id} fullWidth={props.fullWidth}>
      <NumberField
        data-testid="marimo-plugin-number-input"
        className={cn("min-w-[3em]", props.fullWidth && "w-full")}
        minValue={props.start ?? undefined}
        maxValue={props.stop ?? undefined}
        value={value ?? undefined}
        step={props.step}
        onChange={onChange}
        id={id}
        aria-label={props.label || "Number input"}
        isDisabled={props.disabled}
      />
    </Labeled>
  );
};
