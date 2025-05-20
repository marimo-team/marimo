/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import type { IPlugin, IPluginProps, Setter } from "../types";
import { DatePicker } from "@/components/ui/date-picker";
import { type CalendarDate, parseDate } from "@internationalized/date";
import { Labeled } from "./common/labeled";

type T = string;

interface Data {
  label: string | null;
  start: string;
  stop: string;
  step?: string;
  fullWidth: boolean;
  disabled?: boolean;
}

export class DatePickerPlugin implements IPlugin<T, Data> {
  tagName = "marimo-date";

  validator = z.object({
    initialValue: z.string(),
    label: z.string().nullable(),
    start: z.string(),
    stop: z.string(),
    step: z.string().optional(),
    fullWidth: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <DatePickerComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
        disabled={props.data.disabled}
      />
    );
  }
}

interface DatePickerProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const DatePickerComponent = (props: DatePickerProps): JSX.Element => {
  const handleInput = (valueAsDate: CalendarDate | null) => {
    if (!valueAsDate) {
      return;
    }

    const isoStr = valueAsDate.toString();
    props.setValue(isoStr);
  };

  return (
    <Labeled label={props.label} fullWidth={props.fullWidth}>
      <DatePicker
        granularity="day"
        value={parseDate(props.value)}
        onChange={handleInput}
        aria-label={props.label ?? "date picker"}
        minValue={parseDate(props.start)}
        maxValue={parseDate(props.stop)}
        isDisabled={props.disabled}
      />
    </Labeled>
  );
};
