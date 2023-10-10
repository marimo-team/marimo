/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useId, useState } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Slider } from "../../components/ui/slider";
import { Labeled } from "./common/labeled";

type T = number;

interface Data {
  start: T;
  stop: T;
  step?: T;
  label?: string | null;
  debounce: boolean;
}

export class SliderPlugin implements IPlugin<T, Data> {
  tagName = "marimo-slider";

  validator = z.object({
    initialValue: z.number(),
    label: z.string().nullish(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
    debounce: z.boolean().default(false),
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
}: SliderProps): JSX.Element => {
  const id = useId();

  // Hold internal value
  const [internalValue, setInternalValue] = useState(value);
  // Update internal value on prop change
  useEffect(() => {
    setInternalValue(value);
  }, [value]);

  return (
    <Labeled label={label} id={id}>
      <Slider
        id={id}
        className={"relative flex items-center select-none w-36"}
        value={[internalValue]}
        min={start}
        max={stop}
        step={step}
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
    </Labeled>
  );
};
