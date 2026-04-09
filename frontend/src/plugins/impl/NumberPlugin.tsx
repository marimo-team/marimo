/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useCallback, useId } from "react";
import { z } from "zod";
import { NumberField } from "@/components/ui/number-field";
import { useDebounceControlledState } from "@/hooks/useDebounce";
import { cn } from "@/utils/cn";
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

  const initialValue = withoutNaN(props.value);

  // Create a debounced value of 200
  const { value, onChange } = useDebounceControlledState({
    initialValue: initialValue,
    delay: 200,
    disabled: !props.debounce,
    onChange: props.setValue,
  });

  const handleChange = (newValue: number) => {
    onChange(withoutNaN(newValue));
  };

  const step = props.step ?? 1;
  const precision = countDecimals(step);

  const handleIncrement = useCallback(() => {
    const current = toFinite(value, props.start ?? 0);
    let next = roundToPrecision(current + step, precision);
    if (props.stop != null && next > props.stop) {
      next = props.stop;
    }
    handleChange(next);
  }, [value, step, precision, props.start, props.stop]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDecrement = useCallback(() => {
    const current = toFinite(value, props.start ?? 0);
    let next = roundToPrecision(current - step, precision);
    if (props.start != null && next < props.start) {
      next = props.start;
    }
    handleChange(next);
  }, [value, step, precision, props.start, props.stop]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Labeled label={props.label} id={id} fullWidth={props.fullWidth}>
      <NumberField
        data-testid="marimo-plugin-number-input"
        className={cn("min-w-[3em]", props.fullWidth && "w-full")}
        minValue={props.start ?? undefined}
        maxValue={props.stop ?? undefined}
        // This needs to be `?? NaN` since `?? undefined` makes  uncontrolled component
        // and can lead to leaving the old value in forms (https://github.com/marimo-team/marimo/issues/7352)
        // We out NaNs later
        value={value ?? Number.NaN}
        // step is NOT passed to AriaNumberField to avoid React Aria's
        // step-snapping behavior (minValue + n*step) — see #9106
        onChange={handleChange}
        onIncrement={handleIncrement}
        onDecrement={handleDecrement}
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

/** Return value if it's a finite number, otherwise fallback. */
function toFinite(value: number | null | undefined, fallback: number): number {
  if (value == null || !Number.isFinite(value)) {
    return fallback;
  }
  return value;
}

/** Count the decimal digits in a number (e.g. 0.001 → 3). */
function countDecimals(n: number): number {
  const s = String(n);
  const dot = s.indexOf(".");
  return dot === -1 ? 0 : s.length - dot - 1;
}

/** Round to avoid float drift (e.g. 0.1+0.2 → 0.30000000000000004). */
function roundToPrecision(value: number, decimals: number): number {
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}
