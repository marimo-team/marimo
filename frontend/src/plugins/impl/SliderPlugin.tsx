/* Copyright 2024 Marimo. All rights reserved. */
import { useEffect, useId, useState } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Slider } from "../../components/ui/slider";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";
import { prettyNumber } from "@/utils/numbers";

type T = number;

interface Data {
  start: T;
  stop: T;
  step?: T;
  label: string | null;
  debounce: boolean;
  orientation: "horizontal" | "vertical";
  showValue: boolean;
  fullWidth: boolean;
}

export class SliderPlugin implements IPlugin<T, Data> {
  tagName = "marimo-slider";

  validator = z.object({
    initialValue: z.number(),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
    debounce: z.boolean().default(false),
    orientation: z.enum(["horizontal", "vertical"]).default("horizontal"),
    showValue: z.boolean().default(false),
    fullWidth: z.boolean().default(false),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <SliderComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface SliderProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const SliderComponent = ({
  label,
  setValue,
  value,
  start,
  stop,
  step,
  debounce,
  orientation,
  showValue,
  fullWidth,
}: SliderProps): JSX.Element => {
  const id = useId();

  // Hold internal value
  const [internalValue, setInternalValue] = useState(value);
  // Update internal value on prop change
  useEffect(() => {
    setInternalValue(value);
  }, [value]);

  return (
    <div className={fullWidth ? "my-3" : ""}>
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
          />
          {showValue && (
            <div className="text-xs text-muted-foreground min-w-[16px]">
              {prettyNumber(internalValue)}
            </div>
          )}
        </div>
      </Labeled>
    </div>
  );
};
