/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useId } from "react";
import { z } from "zod";
import { NumberField } from "@/components/ui/number-field";
import { useDebounceControlledState } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
import { clamp } from "@/utils/math";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";

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
  public tagName = "marimo-number";

  public validator = z.object({
    initialValue: z.number().nullish(),
    label: z.string().nullable(),
    start: z.number().nullish(),
    stop: z.number().nullish(),
    step: z.number().optional(),
    debounce: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  public render(props: IPluginProps<T | null, Data>): JSX.Element {
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

  const initialValue = withoutNaN(props.value);

  // Create a debounced value of 200
  const { value, onChange } = useDebounceControlledState({
    initialValue: initialValue,
    delay: 200,
    disabled: !props.debounce,
    onChange: props.setValue,
  });

  const clampToRange = (n: number) =>
    clamp(n, props.start ?? -Infinity, props.stop ?? Infinity);

  const handleChange = (newValue: number) => {
    const n = withoutNaN(newValue);
    const next = n == null ? null : clampToRange(n);
    // e.g. typing past `stop` while already at `stop`
    if (next !== value) {
      onChange(next);
    }
  };

  return (
    <Labeled label={props.label} controlId={id} fullWidth={props.fullWidth}>
      <NumberField
        data-testid="marimo-plugin-number-input"
        className={cn("min-w-[3em]", props.fullWidth && "w-full")}
        minValue={props.start ?? undefined}
        maxValue={props.stop ?? undefined}
        // This needs to be `NaN` since `undefined` makes  uncontrolled component
        // and can lead to leaving the old value in forms (https://github.com/marimo-team/marimo/issues/7352)
        // We out NaNs later
        value={value == null ? Number.NaN : clampToRange(value)}
        step={props.step}
        // By default React Aria rounds every value to `start + n * step`, but
        // `step` is only the stepper increment: users can enter any value in
        // range (#9106). "validate" turns off that rounding (and the clamping,
        // done above instead); its step validation is turned off so off-step
        // values aren't flagged invalid or block `mo.ui.form` submission.
        commitBehavior="validate"
        validationBehavior="aria"
        isInvalid={false}
        onChange={handleChange}
        id={id}
        aria-label={props.label || "Number input"}
        isDisabled={props.disabled}
      />
    </Labeled>
  );
};

function withoutNaN(value: number | null | undefined): number | null {
  if (value == null || Number.isNaN(value)) {
    return null;
  }
  return value;
}
