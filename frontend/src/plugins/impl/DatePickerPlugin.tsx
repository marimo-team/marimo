/* Copyright 2024 Marimo. All rights reserved. */
import { useId, useRef } from "react";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { Input } from "../../components/ui/input";
import { Labeled } from "./common/labeled";
import { cn } from "@/utils/cn";

type T = string;

interface Data {
  label: string | null;
  start: string;
  stop: string;
  step?: string;
  fullWidth: boolean;
}

export class DatePickerPlugin implements IPlugin<T, Data> {
  tagName = "marimo-date-picker";

  validator = z.object({
    initialValue: z.string(),
    label: z.string().nullable(),
    start: z.string(),
    stop: z.string(),
    step: z.string().optional(),
    fullWidth: z.boolean().default(false),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <DatePicker
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface DatePickerProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const DatePicker = (props: DatePickerProps): JSX.Element => {
  const inputRef = useRef<HTMLInputElement>(null);
  const handleInput = () => {
    const input = inputRef.current;
    if (input?.valueAsDate) {
      // basic bounds validation; browser validation is lacking
      // when the input's value changes due to keyboard events
      let valueAsDate = input.valueAsDate;
      const minDate = new Date(props.start);
      valueAsDate = valueAsDate < minDate ? minDate : valueAsDate;
      const maxDate = new Date(props.stop);
      valueAsDate = valueAsDate > maxDate ? maxDate : valueAsDate;
      const isoStr = valueAsDate.toISOString();
      // isoStr is of the form YYYY-MM-DDTHH...
      const newValue = isoStr.slice(0, isoStr.indexOf("T"));
      props.setValue(newValue);
    }
  };

  const id = useId();

  return (
    <Labeled label={props.label} id={id} fullWidth={props.fullWidth}>
      <Input
        data-testid="marimo-plugin-date-picker"
        ref={inputRef}
        type="date"
        className={cn({
          "w-full": props.fullWidth,
        })}
        min={props.start}
        max={props.stop}
        value={props.value}
        onInput={handleInput}
        id={id}
      />
    </Labeled>
  );
};
