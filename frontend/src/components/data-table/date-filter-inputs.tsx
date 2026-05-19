/* Copyright 2026 Marimo. All rights reserved. */
import type {
  CalendarDate,
  CalendarDateTime,
  Time,
} from "@internationalized/date";
import { parseDate, parseDateTime, parseTime } from "@internationalized/date";
import type { DateValue, TimeValue } from "react-aria-components";
import { DateField, TimeField } from "@/components/ui/date-input";
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
  const c = aria as CalendarDateTime;
  return new Date(
    c.year,
    c.month - 1,
    c.day,
    c.hour,
    c.minute,
    c.second,
    c.millisecond,
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
      <DateField<CalendarDate>
        aria-label={ariaLabel}
        value={value === undefined ? null : dateToAria("date", value)}
        onChange={handleChange}
        className={className}
      />
    );
  }

  return (
    <DateField<CalendarDateTime>
      aria-label={ariaLabel}
      value={value === undefined ? null : dateToAria("datetime", value)}
      onChange={handleChange}
      className={className}
    />
  );
};
