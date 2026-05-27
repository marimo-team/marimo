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
 * Format a Date as `YYYY-MM-DDTHH:MM:SS` (no timezone suffix) using local
 * fields. See `dateToLocalISODate` for the rationale on local vs UTC.
 */
export function dateToLocalISODateTime(d: Date): string {
  return `${dateToLocalISODate(d)}T${dateToLocalISOTime(d)}`;
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
