/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useId, useRef } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Input } from "../../components/ui/input";
import { Labeled } from "./common/labeled";

type T = number;

interface Data {
  start: T;
  stop: T;
  step?: T;
  label: string | null;
}

export class NumberPlugin implements IPlugin<T, Data> {
  tagName = "marimo-number";

  validator = z.object({
    initialValue: z.number(),
    label: z.string().nullable(),
    start: z.number(),
    stop: z.number(),
    step: z.number().optional(),
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
  const oninput = () => {
    if (inputRef.current !== null) {
      props.setValue(inputRef.current.valueAsNumber);
    }
  };

  useEffect(() => {
    // scrolling inside the input causes the value to change, which
    // is very surprising, so we disable it.
    if (inputRef.current !== null) {
      inputRef.current.addEventListener(
        "wheel",
        (e) => {
          if (e.target === inputRef.current) {
            e.preventDefault();
          }
        },
        { passive: false }
      );
    }
  }, [inputRef]);

  const id = useId();

  return (
    <Labeled label={props.label} id={id}>
      <Input
        className="min-w-[3em]"
        ref={inputRef}
        type="number"
        min={props.start}
        max={props.stop}
        step={props.step}
        value={props.value}
        onInput={oninput}
        id={id}
      />
    </Labeled>
  );
};
