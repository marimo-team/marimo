/* Copyright 2026 Marimo. All rights reserved. */
import { type JSX, useEffect, useId, useMemo, useState } from "react";
import { useLocale } from "react-aria";
import { z } from "zod";
import { NumberField } from "@/components/ui/number-field";
import { cn } from "@/utils/cn";
import {
  maxFractionDigitsForSteps,
  prettyScientificNumber,
  roundToFractionDigits,
} from "@/utils/numbers";
import { Slider } from "../../components/ui/slider";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";

type T = number;

interface Data {
  start: T;
  stop: T;
  step?: T;
  label: string | null;
  steps: T[] | null;
  debounce: boolean;
  orientation: "horizontal" | "vertical";
  showValue: boolean;
  fullWidth: boolean;
  includeInput: boolean;
  disabled?: boolean;
}

export class SliderPlugin implements IPlugin<T, Data> {
  tagName = "marimo-slider";

  validator = z.object({
    initialValue: z.number(),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
    steps: z.array(z.number()).nullable(),
    debounce: z.boolean().default(false),
    orientation: z.enum(["horizontal", "vertical"]).default("horizontal"),
    showValue: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
    includeInput: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    // Create the valueMap function
    const valueMap = (sliderValue: number): number => {
      if (props.data.steps && props.data.steps.length > 0) {
        return props.data.steps[sliderValue];
      }
      return sliderValue;
    };

    return (
      <SliderComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
        valueMap={valueMap}
      />
    );
  }
}

interface SliderProps extends Data {
  value: T;
  setValue: Setter<T>;
  valueMap: (sliderValue: number) => number;
}

interface StepsConfig {
  steps: T[];
  fractionDigits: number;
  minValue: number;
  maxValue: number;
  inputStep: number;
  formatOptions: {
    minimumFractionDigits: number;
    maximumFractionDigits: number;
  };
}

// Index of the step whose value is closest to `target`.
function nearestStepIndex(stepValues: T[], target: number): number {
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let i = 0; i < stepValues.length; i++) {
    const distance = Math.abs(stepValues[i] - target);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = i;
    }
  }
  return bestIndex;
}

// When `steps` are provided, the slider runs in *index* space (start=0,
// stop=len-1, step=1) while the input must display and accept the *actual*
// step values. This config maps the input back into value space.
function computeStepsConfig(steps: T[] | null): StepsConfig | null {
  if (!steps || steps.length === 0) {
    return null;
  }
  const sorted = steps.toSorted((a, b) => a - b);
  // Smallest positive gap between consecutive step values, used as the input's
  // increment/decrement amount. Falls back to 1 when undefined.
  let inputStep = Number.POSITIVE_INFINITY;
  for (let i = 1; i < sorted.length; i++) {
    const gap = sorted[i] - sorted[i - 1];
    if (gap > 0 && gap < inputStep) {
      inputStep = gap;
    }
  }
  if (!Number.isFinite(inputStep) || inputStep <= 0) {
    inputStep = 1;
  }
  const fractionDigits = maxFractionDigitsForSteps(steps, inputStep);
  return {
    steps,
    fractionDigits,
    minValue: roundToFractionDigits(sorted[0], fractionDigits),
    maxValue: roundToFractionDigits(sorted[sorted.length - 1], fractionDigits),
    inputStep: roundToFractionDigits(inputStep, fractionDigits),
    formatOptions: {
      minimumFractionDigits: 0,
      maximumFractionDigits: fractionDigits,
    },
  };
}

const SliderComponent = ({
  label,
  setValue,
  value,
  start,
  stop,
  step,
  steps,
  debounce,
  orientation,
  showValue,
  fullWidth,
  valueMap,
  includeInput,
  disabled,
}: SliderProps): JSX.Element => {
  const id = useId();
  const { locale } = useLocale();

  // Hold internal value
  const [internalValue, setInternalValue] = useState(value);
  // Update internal value on prop change
  useEffect(() => {
    setInternalValue(value);
  }, [value]);

  const stepsConfig = useMemo(() => computeStepsConfig(steps), [steps]);

  const handleInputChange = (nextValue: number | null | undefined): void => {
    if (stepsConfig) {
      const { steps: stepValues, fractionDigits } = stepsConfig;
      // Cleared input -> reset to the first step.
      if (nextValue == null || Number.isNaN(nextValue)) {
        setInternalValue(0);
        setValue(0);
        return;
      }
      const roundedNext = roundToFractionDigits(nextValue, fractionDigits);
      let index = nearestStepIndex(stepValues, roundedNext);
      // If the nearest step is the current one but the value actually moved
      // (e.g. stepper arrows on non-uniform steps), nudge one index in the
      // direction of travel so the input never gets "stuck". Caveat: a typed
      // value closest to the current step but past it nudges too, so on
      // non-uniform steps typing a nearby number can jump to the adjacent step.
      const currentValue = roundToFractionDigits(
        stepValues[internalValue] ?? stepValues[0],
        fractionDigits,
      );
      if (index === internalValue && roundedNext !== currentValue) {
        index =
          roundedNext > currentValue
            ? Math.min(internalValue + 1, stepValues.length - 1)
            : Math.max(internalValue - 1, 0);
      }
      setInternalValue(index);
      setValue(index);
      return;
    }

    // No steps: the input value is the slider value directly.
    const resolved =
      nextValue == null || Number.isNaN(nextValue) ? Number(start) : nextValue;
    setInternalValue(resolved);
    setValue(resolved);
  };

  const inputProps = stepsConfig
    ? {
        // Fall back to the first step when `internalValue` is a stale,
        // out-of-range index (e.g. just after `steps` shrinks).
        value: roundToFractionDigits(
          valueMap(internalValue) ?? stepsConfig.steps[0],
          stepsConfig.fractionDigits,
        ),
        minValue: stepsConfig.minValue,
        maxValue: stepsConfig.maxValue,
        step: stepsConfig.inputStep,
        formatOptions: stepsConfig.formatOptions,
      }
    : {
        value: valueMap(internalValue),
        minValue: start,
        maxValue: stop,
        step,
      };

  const sliderElement = (
    <Labeled
      label={label}
      id={id}
      align={orientation === "horizontal" ? "left" : "top"}
      fullWidth={fullWidth}
      className={cn(fullWidth && "my-1 w-full")}
    >
      <div
        className={cn(
          "flex items-center gap-2",
          orientation === "vertical" &&
            "items-end inline-flex justify-center self-center mx-2",
        )}
      >
        <Slider
          id={id}
          className={cn(
            "relative flex items-center select-none",
            !fullWidth && "data-[orientation=horizontal]:w-36 ",
            "data-[orientation=vertical]:h-36",
          )}
          value={[internalValue]}
          min={start}
          max={stop}
          step={step}
          orientation={orientation}
          // Triggered on all value changes
          onValueChange={([nextValue]) => {
            setInternalValue(nextValue);
            if (!debounce) {
              setValue(nextValue);
            }
          }}
          // Triggered on mouse up
          onValueCommit={([nextValue]) => {
            if (debounce) {
              setValue(nextValue);
            }
          }}
          valueMap={valueMap} // Pass valueMap to Slider
          disabled={disabled}
        />
        {showValue && (
          <div className="text-xs text-muted-foreground min-w-[16px]">
            {prettyScientificNumber(valueMap(internalValue), { locale })}
          </div>
        )}
        {includeInput && (
          <NumberField
            {...inputProps}
            onChange={handleInputChange}
            className="w-24"
            aria-label={`${label || "Slider"} value input`}
            isDisabled={disabled}
          />
        )}
      </div>
    </Labeled>
  );

  return sliderElement;
};
