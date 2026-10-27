/* Copyright 2026 Marimo. All rights reserved. */
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nProvider } from "react-aria";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DatePopover } from "../date-popover";

vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ content }: { content: ReactNode }) => content,
}));

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DatePopover", () => {
  it.each([0, 123])(
    "updates the local timezone and time on rerender with %i milliseconds",
    (milliseconds) => {
      const NativeDateTimeFormat = Intl.DateTimeFormat;
      let systemTimezone = "America/Los_Angeles";
      vi.spyOn(Intl, "DateTimeFormat").mockImplementation(
        function (locales, options) {
          return new NativeDateTimeFormat(locales, {
            ...options,
            timeZone: options?.timeZone ?? systemTimezone,
          });
        },
      );

      const date = new Date("2026-01-15T12:00:00Z");
      date.setUTCMilliseconds(milliseconds);
      const content = () => (
        <I18nProvider locale="en-US">
          <DatePopover date={date} type="datetime">
            timestamp
          </DatePopover>
        </I18nProvider>
      );
      const { rerender } = render(content());
      const previousTime =
        screen.getByText(systemTimezone).nextElementSibling?.textContent;
      const utcTime = screen.getByText("UTC").nextElementSibling?.textContent;

      systemTimezone = "Asia/Tokyo";
      rerender(content());

      const expected = new NativeDateTimeFormat("en-US", {
        timeZone: systemTimezone,
        ...(milliseconds
          ? {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              fractionalSecondDigits: 3,
            }
          : { dateStyle: "long", timeStyle: "medium" }),
      }).format(date);
      expect(screen.queryByText("America/Los_Angeles")).toBeNull();
      expect(
        screen.getByText(systemTimezone).nextElementSibling?.textContent,
      ).toBe(expected);
      expect(expected).not.toBe(previousTime);
      expect(screen.getByText("UTC").nextElementSibling?.textContent).toBe(
        utcTime,
      );
    },
  );
});
