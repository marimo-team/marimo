/* Copyright 2023 Marimo. All rights reserved. */
import { useCallback, useId } from "react";
import { Label } from "../../components/ui/label";
import { z } from "zod";

import { HtmlOutput } from "../../editor/output/HtmlOutput";
import { IPlugin, IPluginProps, Setter } from "../types";
import * as labelStyles from "./Label.styles";
import { Slider } from "../../components/ui/slider";
import clsx from "clsx";

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
  const labelElement =
    props.label === null ? null : (
      <Label htmlFor={id}>
        <HtmlOutput html={props.label} inline={true} />
      </Label>
    );

  return (
    <div className={clsx(labelStyles.labelContainer, "mb-2")}>
      {labelElement}
      <Slider
        className={"relative flex items-center select-none w-36"}
        value={[props.value]}
        min={props.start}
        max={props.stop}
        step={props.step}
        onValueChange={onValueChange}
        id={id}
      />
    </div>
  );
};
