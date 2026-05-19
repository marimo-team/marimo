/* Copyright 2026 Marimo. All rights reserved. */
import type {
  CalendarDate,
  CalendarDateTime,
  Time,
} from "@internationalized/date";
import { parseDate, parseDateTime, parseTime } from "@internationalized/date";
import type { DateValue, TimeValue } from "react-aria-components";
import { MinusIcon } from "lucide-react";
import { TimeField } from "@/components/ui/date-input";
import { DatePicker, DateRangePicker } from "@/components/ui/date-picker";
import {
  dateToISODate,
  dateToISODateTime,
  dateToISOTime,
  type FilterType,
} from "./filters";

export type DateLikeFilterType = Extract<
  FilterType,
  "date" | "datetime" | "time"
>;

function dateToAria(filterType: "date", d: Date): CalendarDate;
function dateToAria(filterType: "datetime", d: Date): CalendarDateTime;
function dateToAria(filterType: "time", d: Date): Time;
function dateToAria(
  filterType: DateLikeFilterType,
  d: Date,
): DateValue | TimeValue {
  switch (filterType) {
    case "date":
      return parseDate(dateToISODate(d));
    case "datetime":
      return parseDateTime(dateToISODateTime(d));
    case "time":
      return parseTime(dateToISOTime(d));
  }
}

function ariaToDate(
  filterType: DateLikeFilterType,
  aria: DateValue | TimeValue,
): Date {
  if (filterType === "time") {
    const t = aria as Time;
    return new Date(1970, 0, 1, t.hour, t.minute, t.second, t.millisecond);
  }
  if (filterType === "date") {
    const c = aria as CalendarDate;
    return new Date(c.year, c.month - 1, c.day);
  }
  const c = aria as Partial<CalendarDateTime> & CalendarDate;
  return new Date(
    c.year,
    c.month - 1,
    c.day,
    c.hour ?? 0,
    c.minute ?? 0,
    c.second ?? 0,
    c.millisecond ?? 0,
  );
}

interface DateLikeInputProps {
  filterType: DateLikeFilterType;
  value: Date | undefined;
  onChange: (value: Date | undefined) => void;
  "aria-label"?: string;
  className?: string;
}

export const DateLikeInput = ({
  filterType,
  value,
  onChange,
  "aria-label": ariaLabel,
  className,
}: DateLikeInputProps) => {
  const handleChange = (next: DateValue | TimeValue | null) => {
    onChange(next === null ? undefined : ariaToDate(filterType, next));
  };

  if (filterType === "time") {
    return (
      <TimeField<Time>
        aria-label={ariaLabel}
        value={value === undefined ? null : dateToAria("time", value)}
        onChange={handleChange}
        className={className}
      />
    );
  }

  if (filterType === "date") {
    return (
      <DatePicker<CalendarDate>
        aria-label={ariaLabel}
        value={value === undefined ? null : dateToAria("date", value)}
        onChange={handleChange}
        className={className}
      />
    );
  }

  return (
    <DatePicker<CalendarDateTime>
      aria-label={ariaLabel}
      value={value === undefined ? null : dateToAria("datetime", value)}
      onChange={handleChange}
      className={className}
    />
  );
};

interface DateLikeRangeInputProps {
  filterType: DateLikeFilterType;
  min: Date | undefined;
  max: Date | undefined;
  onMinChange: (value: Date | undefined) => void;
  onMaxChange: (value: Date | undefined) => void;
  className?: string;
}

export const DateLikeRangeInput = ({
  filterType,
  min,
  max,
  onMinChange,
  onMaxChange,
  className,
}: DateLikeRangeInputProps) => {
  if (filterType === "time") {
    return (
      <div className="flex gap-1 items-center">
        <DateLikeInput
          filterType="time"
          value={min}
          onChange={onMinChange}
          aria-label="min"
          className={className}
        />
        <MinusIcon className="h-5 w-5 text-muted-foreground" />
        <DateLikeInput
          filterType="time"
          value={max}
          onChange={onMaxChange}
          aria-label="max"
          className={className}
        />
      </div>
    );
  }

  const handleChange = (next: { start: DateValue; end: DateValue } | null) => {
    if (next === null) {
      onMinChange(undefined);
      onMaxChange(undefined);
      return;
    }
    onMinChange(ariaToDate(filterType, next.start));
    onMaxChange(ariaToDate(filterType, next.end));
  };

  if (filterType === "date") {
    return (
      <DateRangePicker<CalendarDate>
        aria-label="range"
        value={
          min === undefined || max === undefined
            ? null
            : {
                start: dateToAria("date", min),
                end: dateToAria("date", max),
              }
        }
        onChange={handleChange}
        className={className}
      />
    );
  }

  return (
    <DateRangePicker<CalendarDateTime>
      aria-label="range"
      value={
        min === undefined || max === undefined
          ? null
          : {
              start: dateToAria("datetime", min),
              end: dateToAria("datetime", max),
            }
      }
      onChange={handleChange}
      className={className}
    />
  );
};
