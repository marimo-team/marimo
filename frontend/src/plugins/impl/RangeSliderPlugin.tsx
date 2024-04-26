/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useId, useState } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { RangeSlider } from "../../components/ui/range-slider";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";
import { prettyScientificNumber } from "@/utils/numbers";

type T = number[];

interface Data {
  start: number;
  stop: number;
  step?: number;
  label: string | null;
  steps: T | null;
  debounce: boolean;
  orientation: "horizontal" | "vertical";
  showValue: boolean;
  fullWidth: boolean;
}

export class RangeSliderPlugin implements IPlugin<T, Data> {
  tagName = "marimo-range-slider";

  validator = z.object({
    initialValue: z.array(z.number()),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
    steps: z.array(z.number()).nullable(),
    debounce: z.boolean().default(false),
    orientation: z.enum(["horizontal", "vertical"]).default("horizontal"),
    showValue: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    const valueMap = (sliderValue: number): number => {
      if (props.data.steps && props.data.steps.length > 0) {
        return props.data.steps[sliderValue];
      }
      return sliderValue;
    };

    return (
      <RangeSliderComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
        valueMap={valueMap} // Pass valueMap as a prop
      />
    );
  }
}

interface RangeSliderProps extends Data {
  value: T;
  setValue: Setter<T>;
  valueMap: (sliderValue: number) => number; // Add valueMap to the interface
}

const RangeSliderComponent = ({
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
}: RangeSliderProps): JSX.Element => {
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
    >
      <div
        className={cn(
          "flex items-center gap-2",
          orientation === "vertical" &&
            "items-end inline-flex justify-center self-center mx-2",
        )}
      >
        <RangeSlider
          id={id}
          className={cn(
            "relative flex items-center select-none",
            !fullWidth && "data-[orientation=horizontal]:w-36 ",
            "data-[orientation=vertical]:h-36",
          )}
          value={internalValue}
          min={start}
          max={stop}
          step={step}
          orientation={orientation}
          // Triggered on all value changes
          onValueChange={(nextValue: number[]) => {
            setInternalValue(nextValue);
            if (!debounce) {
              setValue(nextValue);
            }
          }}
          // Triggered on mouse up
          onValueCommit={(nextValue: number[]) => {
            if (debounce) {
              setValue(nextValue);
            }
          }}
          valueMap={valueMap}
        />
        {showValue && (
          <div className="text-xs text-muted-foreground min-w-[16px]">
            {`${prettyScientificNumber(valueMap(internalValue[0]))}, ${prettyScientificNumber(valueMap(internalValue[1]))}`}
          </div>
        )}
      </div>
    </Labeled>
  );

  return fullWidth ? (
    <div className="my-3">{sliderElement}</div>
  ) : (
    sliderElement
  );
};
