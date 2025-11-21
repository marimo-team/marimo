/* Copyright 2024 Marimo. All rights reserved. */

import { isEqual } from "lodash-es";
import { type JSX, useEffect, useId, useState } from "react";
import { z } from "zod";
import { cn } from "@/utils/cn";
import { RangeSlider } from "../../components/ui/range-slider";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";

type T = string[];

interface Data {
  start: number;
  stop: number;
  step: number;
  label: string | null;
  steps: string[];
  debounce: boolean;
  orientation: "horizontal" | "vertical";
  showValue: boolean;
  fullWidth: boolean;
  disabled?: boolean;
}

export class DateSliderPlugin implements IPlugin<T, Data> {
  tagName = "marimo-date-slider";

  validator = z.object({
    initialValue: z.array(z.string()),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number(),
    steps: z.array(z.string()),
    debounce: z.boolean().default(false),
    orientation: z.enum(["horizontal", "vertical"]).default("horizontal"),
    showValue: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    const valueMap = (sliderValue: number): string => {
      if (props.data.steps && props.data.steps.length > 0) {
        return props.data.steps[sliderValue];
      }
      return sliderValue.toString();
    };

    return (
      <DateSliderComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
        valueMap={valueMap}
      />
    );
  }
}

interface DateSliderProps extends Data {
  value: T;
  setValue: Setter<T>;
  valueMap: (sliderValue: number) => string;
}

const DateSliderComponent = ({
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
  disabled,
  valueMap,
}: DateSliderProps): JSX.Element => {
  const id = useId();

  // Convert date strings to indices
  const dateToIndex = (dateStr: string): number => {
    const index = steps.indexOf(dateStr);
    return index !== -1 ? index : 0;
  };

  // Convert internal slider value (indices) to date strings
  const internalValueToDates = (indices: number[]): string[] => {
    return indices.map((idx) => valueMap(idx));
  };

  // Convert date strings to internal slider value (indices)
  const datesToInternalValue = (dates: string[]): number[] => {
    return dates.map((date) => dateToIndex(date));
  };

  // Hold internal value (as indices)
  const [internalValue, setInternalValue] = useState<number[]>(
    datesToInternalValue(value),
  );

  // Update internal value on prop change
  useEffect(() => {
    setInternalValue(datesToInternalValue(value));
  }, [value]);

  const formatDate = (dateStr: string): string => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const sliderElement = (
    <Labeled
      label={label}
      id={id}
      align={orientation === "horizontal" ? "left" : "top"}
      className={cn(fullWidth && "my-1 w-full")}
      fullWidth={fullWidth}
    >
      <div
        className={cn(
          "flex items-center gap-2",
          orientation === "vertical" &&
            "items-end inline-flex justify-center self-center mx-2",
          fullWidth && "w-full",
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
          disabled={disabled}
          // Triggered on all value changes
          onValueChange={(nextValue: number[]) => {
            setInternalValue(nextValue);
            if (!debounce) {
              setValue(internalValueToDates(nextValue));
            }
          }}
          // Triggered on mouse up
          onValueCommit={(nextValue: number[]) => {
            if (debounce) {
              setValue(internalValueToDates(nextValue));
            }
          }}
          // Sometimes onValueCommit doesn't trigger
          // see https://github.com/radix-ui/primitives/issues/1760
          // So we also set the value on pointer/mouse up
          onPointerUp={() => {
            if (
              debounce &&
              !isEqual(internalValue, datesToInternalValue(value))
            ) {
              setValue(internalValueToDates(internalValue));
            }
          }}
          onMouseUp={() => {
            if (
              debounce &&
              !isEqual(internalValue, datesToInternalValue(value))
            ) {
              setValue(internalValueToDates(internalValue));
            }
          }}
          valueMap={(idx: number) => idx}
        />
        {showValue && (
          <div className="text-xs text-muted-foreground min-w-[16px]">
            {`${formatDate(valueMap(internalValue[0]))}, ${formatDate(valueMap(internalValue[1]))}`}
          </div>
        )}
      </div>
    </Labeled>
  );

  return sliderElement;
};
