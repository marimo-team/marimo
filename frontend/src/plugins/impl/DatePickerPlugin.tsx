/* Copyright 2023 Marimo. All rights reserved. */
import { useId, useRef } from "react";
import { Label } from "../../components/ui/label";
import { z } from "zod";

import { IPlugin, IPluginProps, Setter } from "../types";
import { HtmlOutput } from "../../editor/output/HtmlOutput";
import * as labelStyles from "./Label.styles";
import { Input } from "../../components/ui/input";

type T = string;

interface Data {
  label: string | null;
  start: string;
  stop: string;
  step?: string;
}

export class DatePickerPlugin implements IPlugin<T, Data> {
  tagName = "marimo-date-picker";

  validator = z.object({
    initialValue: z.string(),
    label: z.string().nullable(),
    start: z.string(),
    stop: z.string(),
    step: z.string().optional(),
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
    if (inputRef.current !== null && inputRef.current.valueAsDate !== null) {
      // basic bounds validation; browser validation is lacking
      // when the input's value changes due to keyboard events
      let valueAsDate = inputRef.current.valueAsDate;
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
  const labelElement =
    props.label === null ? null : (
      <Label htmlFor={id}>
        <HtmlOutput html={props.label} inline={true} />
      </Label>
    );

  return (
    <div className={labelStyles.labelContainer}>
      {labelElement}
      <Input
        ref={inputRef}
        type="date"
        min={props.start}
        max={props.stop}
        value={props.value}
        onInput={handleInput}
        id={id}
      />
    </div>
  );
};
