/* Copyright 2026 Marimo. All rights reserved. */
import type {
  CalendarDate,
  CalendarDateTime,
  Time,
} from "@internationalized/date";
import { parseDate, parseDateTime, parseTime } from "@internationalized/date";
import { MinusIcon } from "lucide-react";
import { useState } from "react";
import type { DateValue, TimeValue } from "react-aria-components";
import { TimeField } from "@/components/ui/date-input";
import { DatePicker, DateRangePicker } from "@/components/ui/date-picker";
import {
  dateToLocalISODate,
  dateToLocalISODateTime,
  dateToLocalISOTime,
  parseLocalISODate,
  parseLocalISODateTime,
  parseTimeToDate,
} from "@/utils/dates";
import type { FilterType } from "./filters";

export type DateLikeFilterType = Extract<
  FilterType,
  "date" | "datetime" | "time"
>;

function dateToAria(
  filterType: DateLikeFilterType,
  d: Date,
): DateValue | TimeValue {
  switch (filterType) {
    case "date":
      return parseDate(dateToLocalISODate(d));
    case "datetime":
      return parseDateTime(dateToLocalISODateTime(d));
    case "time":
      return parseTime(dateToLocalISOTime(d));
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

// Parses a pasted string into a Date appropriate for the filter type.
// Accepts ISO, US, RFC formats via the Date constructor; time-only strings
// (HH:MM[:SS]) are handled explicitly since `new Date("12:30")` is invalid.
export function parsePastedDate(
  filterType: DateLikeFilterType,
  text: string,
): Date | undefined {
  const trimmed = text.trim();
  if (!trimmed) {
    return undefined;
  }

  if (filterType === "time") {
    const date = parseTimeToDate(trimmed);
    if (date) {
      return date;
    }
  }

  if (filterType === "date") {
    const date = parseLocalISODate(trimmed);
    if (date) {
      return date;
    }
  }

  const isoDateTime = parseLocalISODateTime(trimmed);
  if (isoDateTime) {
    return isoDateTime;
  }

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) {
    return undefined;
  }
  return parsed;
}

export function parsePastedRange(
  filterType: DateLikeFilterType,
  text: string,
): { min: Date; max: Date } | undefined {
  const parts = text.split(/\s+(?:-|–|—|to|and)\s+/i);
  if (parts.length === 2) {
    const min = parsePastedDate(filterType, parts[0]);
    const max = parsePastedDate(filterType, parts[1]);
    if (min && max) {
      return { min, max };
    }
  }
  const single = parsePastedDate(filterType, text);
  if (single) {
    return { min: single, max: single };
  }
  return undefined;
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
  const [seedKey, setSeedKey] = useState(0);
  const [seed, setSeed] = useState(value);

  const handleChange = (next: DateValue | TimeValue | null) => {
    if (next === null) {
      return;
    }
    onChange(ariaToDate(filterType, next));
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    const text = e.clipboardData.getData("text");
    const parsed = parsePastedDate(filterType, text);
    if (!parsed) {
      return;
    }
    e.preventDefault();
    onChange(parsed);
    setSeed(parsed);
    setSeedKey((k) => k + 1);
  };

  const seedValue =
    seed === undefined ? undefined : dateToAria(filterType, seed);

  return (
    <div onPasteCapture={handlePaste} className="contents">
      {filterType === "time" ? (
        <TimeField<Time>
          key={seedKey}
          aria-label={ariaLabel}
          defaultValue={seedValue as Time | undefined}
          hourCycle={24}
          onChange={handleChange}
          className={className}
        />
      ) : filterType === "date" ? (
        <DatePicker<CalendarDate>
          key={seedKey}
          aria-label={ariaLabel}
          defaultValue={seedValue as CalendarDate | undefined}
          onChange={handleChange}
          className={className}
        />
      ) : (
        <DatePicker<CalendarDateTime>
          key={seedKey}
          aria-label={ariaLabel}
          defaultValue={seedValue as CalendarDateTime | undefined}
          granularity="second"
          hourCycle={24}
          onChange={handleChange}
          className={className}
        />
      )}
    </div>
  );
};

interface DateLikeRangeInputProps {
  filterType: DateLikeFilterType;
  min: Date | undefined;
  max: Date | undefined;
  onRangeChange: (min: Date | undefined, max: Date | undefined) => void;
  className?: string;
}

export const DateLikeRangeInput = ({
  filterType,
  min,
  max,
  onRangeChange,
  className,
}: DateLikeRangeInputProps) => {
  const [seedKey, setSeedKey] = useState(0);
  const [seedMin, setSeedMin] = useState(min);
  const [seedMax, setSeedMax] = useState(max);

  const handlePaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    const text = e.clipboardData.getData("text");
    const parsed = parsePastedRange(filterType, text);
    if (!parsed) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    onRangeChange(parsed.min, parsed.max);
    setSeedMin(parsed.min);
    setSeedMax(parsed.max);
    setSeedKey((k) => k + 1);
  };

  if (filterType === "time") {
    return (
      <div onPasteCapture={handlePaste} className="flex gap-1 items-center">
        <DateLikeInput
          key={`min-${seedKey}`}
          filterType="time"
          value={seedMin}
          onChange={(nextMin) => onRangeChange(nextMin, max)}
          aria-label="min"
          className={className}
        />
        <MinusIcon className="h-5 w-5 text-muted-foreground" />
        <DateLikeInput
          key={`max-${seedKey}`}
          filterType="time"
          value={seedMax}
          onChange={(nextMax) => onRangeChange(min, nextMax)}
          aria-label="max"
          className={className}
        />
      </div>
    );
  }

  const handleChange = (next: { start: DateValue; end: DateValue } | null) => {
    if (next === null) {
      return;
    }
    onRangeChange(
      ariaToDate(filterType, next.start),
      ariaToDate(filterType, next.end),
    );
  };

  const seedRange =
    seedMin === undefined || seedMax === undefined
      ? undefined
      : {
          start: dateToAria(filterType, seedMin),
          end: dateToAria(filterType, seedMax),
        };

  return (
    <div onPasteCapture={handlePaste} className="contents">
      {filterType === "date" ? (
        <DateRangePicker<CalendarDate>
          key={seedKey}
          aria-label="range"
          defaultValue={
            seedRange as { start: CalendarDate; end: CalendarDate } | undefined
          }
          onChange={handleChange}
          className={className}
        />
      ) : (
        <DateRangePicker<CalendarDateTime>
          key={seedKey}
          aria-label="range"
          defaultValue={
            seedRange as
              | { start: CalendarDateTime; end: CalendarDateTime }
              | undefined
          }
          granularity="second"
          hourCycle={24}
          onChange={handleChange}
          className={className}
        />
      )}
    </div>
  );
};
