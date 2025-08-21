/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { Tooltip } from "@/components/ui/tooltip";

interface DatePopoverProps {
  date: Date | string | number | null | undefined;
  type: "date" | "datetime";
  children: React.ReactNode;
}

export const DatePopover: React.FC<DatePopoverProps> = ({
  date,
  type,
  children,
}) => {
  // Return just the text if date is invalid
  if (!date || Number.isNaN(new Date(date).getTime())) {
    return children;
  }

  const dateObj = new Date(date);
  const relativeTime = getRelativeTime(dateObj);

  const content = (
    <div className="min-w-[240px] p-1 text-sm">
      <div className="text-muted-foreground mb-2">{relativeTime}</div>
      <div className="space-y-1">
        {type === "datetime" ? (
          Object.entries(getTimezones(dateObj)).map(
            ([timezone, formattedDate]) => (
              <div
                key={timezone}
                className="grid grid-cols-[fit-content(40px)_1fr] gap-4 items-center justify-items-end"
              >
                <span className="bg-muted rounded-md py-1 px-2 w-fit ml-auto">
                  {timezone}
                </span>
                <span>{formattedDate}</span>
              </div>
            ),
          )
        ) : (
          <span>
            {dateObj.toLocaleDateString("en-US", {
              timeZone: "UTC",
              dateStyle: "long",
            })}
          </span>
        )}
      </div>
    </div>
  );

  return (
    <Tooltip content={content} delayDuration={200}>
      <span>{children}</span>
    </Tooltip>
  );
};

function getTimezones(date: Date) {
  const localTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const hasSubSeconds = date.getUTCMilliseconds() !== 0;
  if (hasSubSeconds) {
    return {
      UTC: new Intl.DateTimeFormat("en-US", {
        timeZone: "UTC",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        fractionalSecondDigits: 3,
      }).format(date),
      [localTimezone]: new Intl.DateTimeFormat("en-US", {
        timeZone: localTimezone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        fractionalSecondDigits: 3,
      }).format(date),
    };
  }

  return {
    UTC: new Intl.DateTimeFormat("en-US", {
      timeZone: "UTC",
      dateStyle: "long",
      timeStyle: "medium",
    }).format(date),
    [localTimezone]: new Intl.DateTimeFormat("en-US", {
      timeZone: localTimezone,
      dateStyle: "long",
      timeStyle: "medium",
    }).format(date),
  };
}

/**
 * Converts a date into a human-readable relative time string (e.g. "2 hours ago", "in 5 minutes")
 * Uses Intl.RelativeTimeFormat for localized formatting
 */
function getRelativeTime(date: Date): string {
  // Initialize relative time formatter with English locale and "auto" numeric style
  // "auto" allows for strings like "yesterday" instead of "1 day ago"
  const relativeTimeFormatter = new Intl.RelativeTimeFormat("en", {
    numeric: "auto",
  });

  const currentTime = new Date();
  // Get difference in seconds between now and the input date
  const differenceInSeconds = (currentTime.getTime() - date.getTime()) / 1000;

  // Define time units with their thresholds and conversion factors
  // Format: [threshold before next unit, seconds in this unit, unit name]
  const timeUnits: Array<[number, number, string]> = [
    [60, 1, "second"], // Less than 60 seconds
    [60, 60, "minute"], // Less than 60 minutes
    [24, 3600, "hour"], // Less than 24 hours
    [365, 86_400, "day"], // Less than 365 days
    [Number.POSITIVE_INFINITY, 31_536_000, "year"], // Everything else in years
  ];

  // Find the appropriate unit to use
  for (const [unitThreshold, secondsInUnit, unitName] of timeUnits) {
    const valueInUnits = differenceInSeconds / secondsInUnit;

    if (valueInUnits < unitThreshold) {
      // Convert to fixed decimal and negate since RelativeTimeFormat expects
      // negative values for past times and positive for future times
      const roundedValue = -Number(valueInUnits.toFixed(1));
      return relativeTimeFormatter.format(
        roundedValue,
        unitName as Intl.RelativeTimeFormatUnit,
      );
    }
  }

  // Should never reach here due to Infinity threshold, but provide fallback
  return relativeTimeFormatter.format(0, "second");
}
