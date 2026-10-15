/* Copyright 2026 Marimo. All rights reserved. */

import { TZDate } from "@date-fns/tz";
import { formatDate, isMatch } from "date-fns";
import { Logger } from "./Logger";

export function prettyDate(
  value: string | number | null | undefined,
  type: "date" | "datetime",
  locale: string,
): string {
  if (value == null) {
    return "";
  }

  try {
    // If type is date, drop the timezone by rendering in UTC
    // since dates are absolute
    if (type === "date") {
      return new Date(value).toLocaleDateString(locale, {
        year: "numeric",
        month: "short",
        day: "numeric",
        timeZone: "UTC",
      });
    }

    // For datetime, we keep the original timezone
    return new Date(value).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch (error) {
    Logger.warn("Failed to parse date", error);
    return value.toString();
  }
}

/**
 * If the date has sub-second precision, it should say "2024-10-07 17:15:00.123".
 * Otherwise, it should say "2024-10-07 17:15:00".
 */
export function exactDateTime(
  value: Date,
  timezone: string | undefined,
  locale: string,
): string {
  const hasSubSeconds = value.getUTCMilliseconds() !== 0;
  try {
    if (timezone) {
      const valueWithTimezone = new TZDate(value, timezone);
      const shortTimeZone = getShortTimeZone(timezone, locale);
      if (hasSubSeconds) {
        return `${formatDate(valueWithTimezone, "yyyy-MM-dd HH:mm:ss.SSS")} ${shortTimeZone}`;
      }
      return `${formatDate(valueWithTimezone, "yyyy-MM-dd HH:mm:ss")} ${shortTimeZone}`;
    }

    if (hasSubSeconds) {
      return formatDate(value, "yyyy-MM-dd HH:mm:ss.SSS");
    }

    return formatDate(value, "yyyy-MM-dd HH:mm:ss");
  } catch (error) {
    Logger.warn("Failed to parse date", error);
    return value.toISOString();
  }
}

export function getShortTimeZone(timezone: string, locale: string): string {
  try {
    const abbrev = new Intl.DateTimeFormat(locale, {
      timeZone: timezone,
      timeZoneName: "short",
    })
      .formatToParts(new Date())
      .find((part) => part.type === "timeZoneName")?.value;
    return abbrev ?? "";
  } catch (error) {
    Logger.warn("Failed to get abbrev", error);
    return timezone;
  }
}

/**
 * If today, it should say "Today at 8:00 AM".
 *
 * If yesterday, it should say "Yesterday at 8:00 AM".
 *
 * If a date in the past, it should say "<date> at 8:00 AM".
 */
export function timeAgo(
  value: string | number | null | undefined,
  locale: string,
): string {
  if (value == null) {
    return "";
  }
  if (value === 0) {
    return "";
  }

  try {
    const date = new Date(value);
    const today = new Date();
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {
      return `Today at ${date.toLocaleTimeString(locale, {
        hour: "numeric",
        minute: "numeric",
      })}`;
    }
    if (date.toDateString() === yesterday.toDateString()) {
      return `Yesterday at ${date.toLocaleTimeString(locale, {
        hour: "numeric",
        minute: "numeric",
      })}`;
    }
    return `${date.toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
    })} at ${date.toLocaleTimeString(locale, {
      hour: "numeric",
      minute: "numeric",
    })}`;
  } catch (error) {
    Logger.warn("Failed to parse date", error);
  }

  return value.toString();
}

function pad2(n: number): string {
  return n.toString().padStart(2, "0");
}

function pad4(n: number): string {
  return n.toString().padStart(4, "0");
}

/**
 * Format a Date as `YYYY-MM-DD` using the date's local-time fields.
 *
 * The output reflects what the user sees in their own timezone (the calendar
 * day on their clock), not the UTC day. Use this when round-tripping values
 * that originated from local-time inputs — date pickers, "filter on this
 * day", calendar UI — so the displayed and serialized days agree.
 *
 * Not suitable for cross-timezone storage; use `Date.toISOString()` for that.
 */
export function dateToLocalISODate(d: Date): string {
  return `${pad4(d.getFullYear())}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

/**
 * Format a Date as `HH:MM:SS` using the date's local-time fields.
 *
 * See `dateToLocalISODate` for the rationale on local vs UTC.
 */
export function dateToLocalISOTime(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

/**
 * Parse a time string into a Date anchored at the Unix epoch day. Supports
 * the backend's wire format (`HH:MM:SS`, as produced by `dateToLocalISOTime`)
 * as well as looser pasted text: optional seconds, optional milliseconds,
 * and an optional `am`/`pm` suffix (e.g. `"14:30"`, `"2:30 PM"`,
 * `"14:30:00.123"`).
 */
export function parseTimeToDate(value: string): Date | undefined {
  const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.(\d+))?\s*(am|pm)?$/i.exec(
    value.trim(),
  );
  if (!match) {
    return undefined;
  }
  const [, hStr, mStr, sStr, msStr, ampm] = match;
  let hour = Number.parseInt(hStr, 10);
  const minute = Number.parseInt(mStr, 10);
  const second = sStr ? Number.parseInt(sStr, 10) : 0;
  const ms = msStr ? Number.parseInt(msStr.padEnd(3, "0").slice(0, 3), 10) : 0;
  if (minute > 59 || second > 59) {
    return undefined;
  }
  if (ampm) {
    if (hour < 1 || hour > 12) {
      return undefined;
    }
    const isPm = ampm.toLowerCase() === "pm";
    if (hour === 12) {
      hour = isPm ? 12 : 0;
    } else if (isPm) {
      hour += 12;
    }
  } else if (hour > 23) {
    return undefined;
  }
  return new Date(1970, 0, 1, hour, minute, second, ms);
}

/**
 * Format a Date as `YYYY-MM-DDTHH:MM:SS` (no timezone suffix) using local
 * fields. See `dateToLocalISODate` for the rationale on local vs UTC.
 */
export function dateToLocalISODateTime(d: Date): string {
  return `${dateToLocalISODate(d)}T${dateToLocalISOTime(d)}`;
}

/**
 * Parse a `YYYY-MM-DD` string into a Date anchored at local midnight.
 *
 * Unlike `new Date("YYYY-MM-DD")`, which the spec parses as UTC midnight,
 * this treats the string as a calendar date in the viewer's own timezone.
 * Returns undefined if the string doesn't match, or encodes a calendar
 * date that doesn't exist (e.g. month 13, Feb 30), since `Date` would
 * otherwise silently roll those over into a different date.
 */
export function parseLocalISODate(value: string): Date | undefined {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) {
    return undefined;
  }
  const [, yStr, mStr, dStr] = match;
  const year = Number.parseInt(yStr, 10);
  const month = Number.parseInt(mStr, 10);
  const day = Number.parseInt(dStr, 10);
  const date = new Date(year, month - 1, day);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return undefined;
  }
  return date;
}

/**
 * Parse an ISO-ish `YYYY-MM-DD[T ]HH:MM[:SS[.sss]][Z|+HH:MM]` datetime string
 * as wall-clock local time, ignoring any trailing `Z` or UTC offset.
 *
 * This keeps pasted datetimes consistent with the date/time pickers' local-
 * time basis: pasting `2024-01-15T08:30:00Z` displays `08:30` instead of
 * being shifted by the viewer's timezone.
 */
export function parseLocalISODateTime(value: string): Date | undefined {
  const match =
    /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?$/.exec(
      value.trim(),
    );
  if (!match) {
    return undefined;
  }
  const [, yStr, moStr, dStr, hStr, miStr, sStr] = match;
  return new Date(
    Number.parseInt(yStr, 10),
    Number.parseInt(moStr, 10) - 1,
    Number.parseInt(dStr, 10),
    Number.parseInt(hStr, 10),
    Number.parseInt(miStr, 10),
    sStr ? Number.parseInt(sStr, 10) : 0,
  );
}

export const supportedDateFormats = ["yyyy", "yyyy-MM", "yyyy-MM-dd"] as const;
export type DateFormat = (typeof supportedDateFormats)[number];

/**
 * If the string matches one of the supported date formats, return the format.
 */
export function getDateFormat(value: string): DateFormat | null {
  for (const format of supportedDateFormats) {
    if (isMatch(value, format)) {
      return format;
    }
  }
  return null;
}
