/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import type { IPlugin, IPluginProps, Setter } from "../types";
import { DateRangePicker } from "@/components/ui/date-picker";
import { type CalendarDate, parseDate } from "@internationalized/date";
import { Labeled } from "./common/labeled";

type T = [string, string];

interface Data {
  label: string | null;
  start: string;
  stop: string;
  step?: string;
  fullWidth: boolean;
  disabled?: boolean;
}

export class DateRangePickerPlugin implements IPlugin<T, Data> {
  tagName = "marimo-date-range";

  validator = z.object({
    initialValue: z.tuple([z.string(), z.string()]),
    label: z.string().nullable(),
    start: z.string(),
    stop: z.string(),
    step: z.string().optional(),
    fullWidth: z.boolean().default(false),
    disabled: z.boolean().optional(),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <DateRangePickerComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      />
    );
  }
}

interface DateRangePickerProps extends Data {
  value: T;
  setValue: Setter<T>;
}

const DateRangePickerComponent = (props: DateRangePickerProps): JSX.Element => {
  const handleInput = (
    valueAsDateRange: {
      start: CalendarDate;
      end: CalendarDate;
    } | null,
  ) => {
    if (!valueAsDateRange) {
      return;
    }

    const { start, end } = valueAsDateRange;
    const isoStrRange: T = [start.toString(), end.toString()];
    props.setValue(isoStrRange);
  };

  return (
    <Labeled label={props.label} fullWidth={props.fullWidth}>
      <DateRangePicker
        granularity="day"
        value={{
          start: parseDate(props.value[0]),
          end: parseDate(props.value[1]),
        }}
        onChange={handleInput}
        aria-label={props.label ?? "date range picker"}
        minValue={parseDate(props.start)}
        maxValue={parseDate(props.stop)}
        isDisabled={props.disabled}
      />
    </Labeled>
  );
};
