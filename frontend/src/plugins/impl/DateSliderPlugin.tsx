/* Copyright 2024 Marimo. All rights reserved. */

import { isEqual } from "lodash-es";
import { type JSX, useEffect, useId, useState } from "react";
import { z } from "zod";
import { cn } from "@/utils/cn";
import { DateSlider } from "../../components/ui/date-slider";
import type { IPlugin, IPluginProps, Setter } from "../types";
import { Labeled } from "./common/labeled";

// Value type is array of two date strings
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
    return (
      <DateSliderComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface DateSliderProps extends Data {
  value: T;
  setValue: Setter<T>;
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
}: DateSliderProps): JSX.Element => {
  const id = useId();

  // Convert date string to index in steps array
  const dateToIndex = (dateStr: string): number => {
    const index = steps.indexOf(dateStr);
    return index !== -1 ? index : 0;
  };

  // Convert index to date string
  const indexToDate = (index: number): string => {
    return steps[index] || steps[0];
  };

  // Convert value (date strings) to internal value (indices)
  const valueToIndices = (dateValue: T): number[] => {
    if (!dateValue || dateValue.length !== 2) {
      return [start, stop];
    }
    return [dateToIndex(dateValue[0]), dateToIndex(dateValue[1])];
  };

  // Convert internal value (indices) to value (date strings)
  const indicesToValue = (indices: number[]): T => {
    // Ensure the indices are in the correct order (min, max)
    const [idx0, idx1] = indices;
    const minIdx = Math.min(idx0, idx1);
    const maxIdx = Math.max(idx0, idx1);
    return [indexToDate(minIdx), indexToDate(maxIdx)];
  };

  // Hold internal value as indices
  const [internalValue, setInternalValue] = useState<number[]>(() => {
    const indices = valueToIndices(value);
    // Ensure initial value is ordered correctly
    return [Math.min(indices[0], indices[1]), Math.max(indices[0], indices[1])];
  });

  // Update internal value when prop changes
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    const indices = valueToIndices(value);
    // Ensure the values are ordered correctly
    const orderedIndices = [
      Math.min(indices[0], indices[1]),
      Math.max(indices[0], indices[1]),
    ];
    setInternalValue(orderedIndices);
  }, [value, steps]);

  return (
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
        <DateSlider
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
              setValue(indicesToValue(nextValue));
            }
          }}
          // Triggered on mouse up
          onValueCommit={(nextValue: number[]) => {
            if (debounce) {
              setValue(indicesToValue(nextValue));
            }
          }}
          // Sometimes onValueCommit doesn't trigger
          // see https://github.com/radix-ui/primitives/issues/1760
          // So we also set the value on pointer/mouse up
          onPointerUp={() => {
            if (debounce && !isEqual(internalValue, valueToIndices(value))) {
              setValue(indicesToValue(internalValue));
            }
          }}
          onMouseUp={() => {
            if (debounce && !isEqual(internalValue, valueToIndices(value))) {
              setValue(indicesToValue(internalValue));
            }
          }}
          valueMap={(idx: number) => {
            // Convert index to date string for tooltip display
            return indexToDate(idx);
          }}
        />
        {showValue && (
          <div className="text-xs text-muted-foreground min-w-[16px]">
            {`(${indexToDate(internalValue[0])}, ${indexToDate(internalValue[1])})`}
          </div>
        )}
      </div>
    </Labeled>
  );
};
