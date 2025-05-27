/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import type { IPlugin, IPluginProps, Setter } from "../types";
import { DatePicker } from "@/components/ui/date-picker";
import { type CalendarDateTime, parseDateTime } from "@internationalized/date";
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

export class DateTimePickerPlugin implements IPlugin<T, Data> {
  tagName = "marimo-datetime";

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
      <DateTimePickerComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface DateTimePickerProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const DateTimePickerComponent = (props: DateTimePickerProps): JSX.Element => {
  const handleInput = (valueAsDateTime: CalendarDateTime | null) => {
    if (!valueAsDateTime) {
      return;
    }

    const isoStr = valueAsDateTime.toString();
    props.setValue(isoStr);
  };

  // Add null check and default to undefined when no value is provided
  const parsedValue = props.value ? parseDateTime(props.value) : undefined;

  return (
    <Labeled label={props.label} fullWidth={props.fullWidth}>
      <DatePicker
        granularity="minute"
        value={parsedValue}
        onChange={handleInput}
        aria-label={props.label ?? "date time picker"}
        minValue={parseDateTime(props.start)}
        maxValue={parseDateTime(props.stop)}
        isDisabled={props.disabled}
      />
    </Labeled>
  );
};
