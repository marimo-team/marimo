/* Copyright 2024 Marimo. All rights reserved. */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  exactDateTime,
  getDateFormat,
  getShortTimeZone,
  prettyDate,
  timeAgo,
} from "../dates";

const locale = "en-US";

describe("dates", () => {
  // Save original timezone
  let originalTimezone: string | undefined;

  // Set up a fixed timezone for tests
  beforeAll(() => {
    originalTimezone = process.env.TZ;
    process.env.TZ = "UTC";
  });

  // Restore original timezone
  afterAll(() => {
    process.env.TZ = originalTimezone;
  });

  describe("prettyDate", () => {
    it("returns empty string for null or undefined", () => {
      expect(prettyDate(null, "date", locale)).toBe("");
      expect(prettyDate(undefined, "date", locale)).toBe("");
    });

    it("formats date correctly", () => {
      const date = new Date("2023-05-15T12:00:00Z");
      // Using a regex to match the pattern since exact format may vary by locale
      expect(prettyDate(date.toISOString(), "date", locale)).toMatch(
        /May 15, 2023/,
      );
    });

    it("formats datetime correctly", () => {
      const date = new Date("2023-05-15T12:00:00Z");
      expect(prettyDate(date.toISOString(), "datetime", locale)).toMatch(
        /May 15, 2023/,
      );
    });

    it("handles errors gracefully", () => {
      expect(prettyDate("invalid-date", "date", locale)).toBe("Invalid Date");
    });

    it("handles numeric timestamp input", () => {
      const timestamp = 1_684_152_000_000; // 2023-05-15T12:00:00Z in milliseconds
      expect(prettyDate(timestamp, "date", locale)).toMatch(/May 15, 2023/);
    });

    it("preserves timezone for datetime type", () => {
      // This date is in winter time to avoid daylight saving time issues
      const date = new Date("2023-01-15T15:30:00Z");
      expect(prettyDate(date.toISOString(), "datetime", locale)).toMatch(
        /Jan 15, 2023/,
      );
    });

    it("drops timezone for date type by using UTC", () => {
      // Create a date that would be different days in different timezones
      const date = new Date("2023-05-15T23:30:00Z"); // Late in the day UTC
      expect(prettyDate(date.toISOString(), "date", locale)).toMatch(
        /May 15, 2023/,
      );
    });

    describe("with different locales", () => {
      // Save original implementation
      // eslint-disable-next-line @typescript-eslint/unbound-method
      const originalToLocaleDateString = Date.prototype.toLocaleDateString;

      afterAll(() => {
        // Restore original implementation
        Date.prototype.toLocaleDateString = originalToLocaleDateString;
      });

      it("formats date in fr-FR locale", () => {
        // Mock toLocaleDateString to simulate fr-FR locale
        // @ts-expect-error - we are mocking the method
        Date.prototype.toLocaleDateString = (locale, options) => {
          if (options?.timeZone === "UTC") {
            return "15 mai 2023";
          }
          return "15 mai 2023";
        };

        const date = new Date("2023-05-15T12:00:00Z");
        expect(prettyDate(date.toISOString(), "date", locale)).toBe(
          "15 mai 2023",
        );
      });
    });
  });

  describe("exactDateTime", () => {
    it("formats date without milliseconds", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, undefined, locale)).toBe(
        "2023-05-15 12:00:00",
      );
    });

    it("formats date with milliseconds", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, undefined, locale)).toBe(
        "2023-05-15 12:00:00.123",
      );
    });

    it("formats date in UTC when renderInUTC is true", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, "UTC", locale)).toBe(
        "2023-05-15 12:00:00 UTC",
      );
    });

    it("formats date with milliseconds in UTC when renderInUTC is true", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, "UTC", locale)).toBe(
        "2023-05-15 12:00:00.123 UTC",
      );
    });

    it("formats date in America/New_York timezone", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, "America/New_York", locale)).toBe(
        "2023-05-15 08:00:00 EDT",
      );
    });

    it("formats date with milliseconds in America/New_York timezone", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, "America/New_York", locale)).toBe(
        "2023-05-15 08:00:00.123 EDT",
      );
    });
  });

  describe("timeAgo", () => {
    it("returns empty string for null, undefined, or 0", () => {
      expect(timeAgo(null, locale)).toBe("");
      expect(timeAgo(undefined, locale)).toBe("");
      expect(timeAgo(0, locale)).toBe("");
    });

    it("formats today's date correctly", () => {
      const today = new Date();
      const result = timeAgo(today.toISOString(), locale);
      expect(result).toMatch(/Today at/);
    });

    it("formats yesterday's date correctly", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const result = timeAgo(yesterday.toISOString(), locale);
      expect(result).toMatch(/Yesterday at/);
    });

    it("formats older dates correctly", () => {
      const oldDate = new Date("2020-01-01T12:00:00Z");
      const result = timeAgo(oldDate.toISOString(), locale);
      expect(result).toMatch(/Jan 1, 2020 at/);
    });

    it("handles errors gracefully", () => {
      expect(timeAgo("invalid-date", locale)).toBe(
        "Invalid Date at Invalid Date",
      );
    });
  });

  describe("getShortTimeZone", () => {
    it("returns the short timezone", () => {
      expect(getShortTimeZone("America/New_York", locale)).toBeOneOf([
        "EDT",
        "EST",
      ]);
    });

    it("handles errors gracefully", () => {
      expect(getShortTimeZone("MarimoLand", locale)).toBe("MarimoLand");
    });
  });

  describe("getDateFormat", () => {
    it("returns the correct format for date", () => {
      expect(getDateFormat("2023-05-15")).toBe("yyyy-MM-dd");
    });

    it("returns the correct format for year only", () => {
      expect(getDateFormat("2023")).toBe("yyyy");
    });

    it("returns the correct format for month only", () => {
      expect(getDateFormat("2023-05")).toBe("yyyy-MM");
    });

    it("returns null for invalid date", () => {
      expect(getDateFormat("2023-05-15T12:00:00Z")).toBeNull();
    });
  });
});
