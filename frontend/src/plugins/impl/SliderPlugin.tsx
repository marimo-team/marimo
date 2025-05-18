/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useId, useState } from "react";
import { z } from "zod";

import type { IPlugin, IPluginProps, Setter } from "../types";
import { Slider } from "../../components/ui/slider";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";
import { prettyScientificNumber } from "@/utils/numbers";
import { NumberField } from "@/components/ui/number-field";

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

  // Hold internal value
  const [internalValue, setInternalValue] = useState(value);
  // Update internal value on prop change
  useEffect(() => {
    setInternalValue(value);
  }, [value]);

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
            {prettyScientificNumber(valueMap(internalValue))}
          </div>
        )}
        {includeInput && (
          <NumberField
            value={valueMap(internalValue)}
            onChange={(nextValue) => {
              setInternalValue(nextValue);
              if (!debounce) {
                setValue(nextValue);
              }
            }}
            minValue={start}
            maxValue={stop}
            step={step}
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
