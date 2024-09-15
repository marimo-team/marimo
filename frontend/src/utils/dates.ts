/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "./Logger";

export function prettyDate(value: string | number | null | undefined): string {
  if (value == null) {
    return "";
  }

  try {
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
