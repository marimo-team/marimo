/* Copyright 2023 Marimo. All rights reserved. */
import { useCallback, useId } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Slider } from "../../components/ui/slider";
import { Labeled } from "./common/labeled";

type T = number;

interface Data {
  start: T;
  stop: T;
  step?: T;
  label: string | null;
}

export class SliderPlugin implements IPlugin<T, Data> {
  tagName = "marimo-slider";

  validator = z.object({
    initialValue: z.number(),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
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

const SliderComponent = (props: SliderProps): JSX.Element => {
  const setValue = props.setValue;
  const onValueChange = useCallback(
    (values: number[]) => {
      setValue(values[0]);
    },
    [setValue]
  );
  const id = useId();

  return (
    <Labeled label={props.label} id={id}>
      <Slider
        className={"relative flex items-center select-none w-36"}
        value={[props.value]}
        min={props.start}
        max={props.stop}
        step={props.step}
        onValueChange={onValueChange}
        id={id}
      />
    </Labeled>
  );
};
