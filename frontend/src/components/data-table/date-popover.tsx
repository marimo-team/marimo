/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { useDateFormatter, useLocale } from "react-aria";
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

  const content = (
    <div className="min-w-[240px] p-1 text-sm">
      <div className="text-muted-foreground mb-2">
        <RelativeTime date={dateObj} />
      </div>
      <div className="space-y-1">
        {type === "datetime" ? (
          <TimezoneDisplay date={dateObj} />
        ) : (
          <DateDisplay date={dateObj} />
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

const TimezoneDisplay = ({ date }: { date: Date }) => {
  const { locale } = useLocale();
  const localTimezone = Intl.DateTimeFormat(locale).resolvedOptions().timeZone;
  const hasSubSeconds = date.getUTCMilliseconds() !== 0;

  const utcFormatter = useDateFormatter(
    hasSubSeconds
      ? {
          timeZone: "UTC",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          fractionalSecondDigits: 3,
        }
      : {
          timeZone: "UTC",
          dateStyle: "long",
          timeStyle: "medium",
        },
  );

  const localFormatter = useDateFormatter(
    hasSubSeconds
      ? {
          timeZone: localTimezone,
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          fractionalSecondDigits: 3,
        }
      : {
          timeZone: localTimezone,
          dateStyle: "long",
          timeStyle: "medium",
        },
  );

  return (
    <>
      <div className="grid grid-cols-[fit-content(40px)_1fr] gap-4 items-center justify-items-end">
        <span className="bg-muted rounded-md py-1 px-2 w-fit ml-auto">UTC</span>
        <span>{utcFormatter.format(date)}</span>
      </div>
      <div className="grid grid-cols-[fit-content(40px)_1fr] gap-4 items-center justify-items-end">
        <span className="bg-muted rounded-md py-1 px-2 w-fit ml-auto">
          {localTimezone}
        </span>
        <span>{localFormatter.format(date)}</span>
      </div>
    </>
  );
};

const DateDisplay = ({ date }: { date: Date }) => {
  const dateFormatter = useDateFormatter({
    timeZone: "UTC",
    dateStyle: "long",
  });

  return <span>{dateFormatter.format(date)}</span>;
};

const RelativeTime = ({ date }: { date: Date }) => {
  const { locale } = useLocale();

  // Initialize relative time formatter with current locale and "auto" numeric style
  const relativeTimeFormatter = new Intl.RelativeTimeFormat(locale, {
    numeric: "auto",
  });

  const currentTime = new Date();
  // Get difference in seconds between now and the input date
  const differenceInSeconds = (currentTime.getTime() - date.getTime()) / 1000;

  // Define time units with their thresholds and conversion factors
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
      return (
        <span>
          {relativeTimeFormatter.format(
            roundedValue,
            unitName as Intl.RelativeTimeFormatUnit,
          )}
        </span>
      );
    }
  }

  // Should never reach here due to Infinity threshold, but provide fallback
  return <span>{relativeTimeFormatter.format(0, "second")}</span>;
};
