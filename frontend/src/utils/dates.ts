/* Copyright 2024 Marimo. All rights reserved. */
import { formatDate } from "date-fns";
import { TZDate } from "@date-fns/tz";
import { Logger } from "./Logger";

export function prettyDate(
  value: string | number | null | undefined,
  type: "date" | "datetime",
): string {
  if (value == null) {
    return "";
  }

  try {
    // If type is date, drop the timezone by rendering in UTC
    // since dates are absolute
    if (type === "date") {
      value = new Date(value).toLocaleDateString(undefined, {
        timeZone: "UTC",
      });
    }

    return new Date(value).toLocaleDateString(undefined, {
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
): string {
  const hasSubSeconds = value.getUTCMilliseconds() !== 0;
  try {
    if (timezone) {
      const valueWithTimezone = new TZDate(value, timezone);
      const shortTimeZone = getShortTimeZone(timezone);
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

export function getShortTimeZone(timezone: string): string {
  try {
    const abbrev = new Intl.DateTimeFormat("en-US", {
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
export function timeAgo(value: string | number | null | undefined): string {
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
      return `Today at ${date.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "numeric",
      })}`;
    }
    if (date.toDateString() === yesterday.toDateString()) {
      return `Yesterday at ${date.toLocaleTimeString(undefined, {
        hour: "numeric",
        minute: "numeric",
      })}`;
    }
    return `${date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    })} at ${date.toLocaleTimeString(undefined, {
      hour: "numeric",
      minute: "numeric",
    })}`;
  } catch (error) {
    Logger.warn("Failed to parse date", error);
  }

  return value.toString();
}
