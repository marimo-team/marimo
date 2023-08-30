/* Copyright 2023 Marimo. All rights reserved. */
import { useId, useRef } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Input } from "../../components/ui/input";
import { Labeled } from "./common/labeled";
import { useDebounceControlledState } from "@/hooks/useDebounce";

type T = number;

interface Data {
  start: T;
  stop: T;
  step?: T;
  label: string | null;
  debounce: boolean;
}

export class NumberPlugin implements IPlugin<T, Data> {
  tagName = "marimo-number";

  validator = z.object({
    initialValue: z.number(),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
    debounce: z.boolean().default(false),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
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
  value: T;
  setValue: Setter<T>;
}

const NumberComponent = (props: NumberComponentProps): JSX.Element => {
  const inputRef = useRef<HTMLInputElement>(null);
  const id = useId();

  // Create a debounced value of 200
  const { value, onChange } = useDebounceControlledState({
    initialValue: props.value,
    delay: 200,
    disabled: !props.debounce,
    onChange: props.setValue,
  });

  return (
    <Labeled label={props.label} id={id}>
      <Input
        className="min-w-[3em]"
        ref={inputRef}
        type="number"
        min={props.start}
        max={props.stop}
        step={props.step}
        value={value}
        onWheel={(e) => {
          e.preventDefault();
        }}
        onChange={(e) => {
          onChange(e.target.valueAsNumber);
        }}
        id={id}
      />
    </Labeled>
  );
};
