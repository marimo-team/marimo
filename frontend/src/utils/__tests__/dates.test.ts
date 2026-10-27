/* Copyright 2026 Marimo. All rights reserved. */
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  exactDateTime,
  getDateFormat,
  getShortTimeZone,
  parseLocalISODate,
  parseLocalISODateTime,
  parseTimeToDate,
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
      // oxlint-disable-next-line typescript/unbound-method
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
      expect(exactDateTime(date, "America/New_York", locale)).toBeOneOf([
        "2023-05-15 08:00:00 EDT",
        "2023-05-15 08:00:00 EST",
      ]);
    });

    it("formats date with milliseconds in America/New_York timezone", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, "America/New_York", locale)).toBeOneOf([
        "2023-05-15 08:00:00.123 EDT",
        "2023-05-15 08:00:00.123 EST",
      ]);
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

  describe("parseTimeToDate", () => {
    it("parses 24-hour times", () => {
      expect(parseTimeToDate("14:30")).toEqual(new Date(1970, 0, 1, 14, 30));
      expect(parseTimeToDate("14:30:05")).toEqual(
        new Date(1970, 0, 1, 14, 30, 5),
      );
    });

    it("parses times with an am/pm suffix", () => {
      expect(parseTimeToDate("2:30 PM")).toEqual(new Date(1970, 0, 1, 14, 30));
      expect(parseTimeToDate("12:00 am")).toEqual(new Date(1970, 0, 1, 0, 0));
      expect(parseTimeToDate("12:00 pm")).toEqual(new Date(1970, 0, 1, 12, 0));
    });

    it("rejects an out-of-range hour instead of letting Date normalize it", () => {
      // new Date(1970, 0, 1, 25, 0) would silently become 01:00 the next day.
      expect(parseTimeToDate("25:00")).toBeUndefined();
    });

    it("rejects an out-of-range minute instead of letting Date normalize it", () => {
      // new Date(1970, 0, 1, 12, 99) would silently become 13:39.
      expect(parseTimeToDate("12:99")).toBeUndefined();
    });

    it("rejects an out-of-range second", () => {
      expect(parseTimeToDate("12:30:99")).toBeUndefined();
    });

    it("requires an hour from 1 to 12 with an am/pm suffix", () => {
      expect(parseTimeToDate("0:30 am")).toBeUndefined();
      expect(parseTimeToDate("13:30 pm")).toBeUndefined();
    });

    it("parses milliseconds", () => {
      expect(parseTimeToDate("14:30:05.123")).toEqual(
        new Date(1970, 0, 1, 14, 30, 5, 123),
      );
    });

    it("pads a short millisecond fraction and truncates a long one", () => {
      expect(parseTimeToDate("14:30:05.5")).toEqual(
        new Date(1970, 0, 1, 14, 30, 5, 500),
      );
      expect(parseTimeToDate("14:30:05.123456")).toEqual(
        new Date(1970, 0, 1, 14, 30, 5, 123),
      );
    });
  });

  describe("parseLocalISODate", () => {
    it("parses a date-only string into local midnight", () => {
      expect(parseLocalISODate("2024-01-15")).toEqual(new Date(2024, 0, 15));
    });

    it("returns undefined for a non-date-only string", () => {
      expect(parseLocalISODate("2024-01-15T00:00:00")).toBeUndefined();
      expect(parseLocalISODate("")).toBeUndefined();
      expect(parseLocalISODate("not-a-date")).toBeUndefined();
    });

    it("returns undefined for a calendar date that doesn't exist", () => {
      expect(parseLocalISODate("2024-02-30")).toBeUndefined();
      expect(parseLocalISODate("2024-13-01")).toBeUndefined();
    });
  });

  describe("parseLocalISODateTime", () => {
    it("parses a 'T'-separated datetime into local wall-clock time", () => {
      expect(parseLocalISODateTime("2024-01-15T08:30:00")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
    });

    it("parses a space-separated datetime", () => {
      expect(parseLocalISODateTime("2024-01-15 08:30:00")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
    });

    it("defaults seconds to 0 when omitted", () => {
      expect(parseLocalISODateTime("2024-01-15T08:30")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
    });

    it("ignores a trailing Z instead of shifting to UTC", () => {
      expect(parseLocalISODateTime("2024-01-15T08:30:00Z")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
    });

    it("ignores a trailing UTC offset instead of shifting the time", () => {
      expect(parseLocalISODateTime("2024-01-15T08:30:00+05:00")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
      expect(parseLocalISODateTime("2024-01-15T08:30:00-0500")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
    });

    it("ignores sub-second precision", () => {
      expect(parseLocalISODateTime("2024-01-15T08:30:00.123")).toEqual(
        new Date(2024, 0, 15, 8, 30, 0),
      );
    });

    it("returns undefined for a date-only or unparsable string", () => {
      expect(parseLocalISODateTime("2024-01-15")).toBeUndefined();
      expect(parseLocalISODateTime("not-a-datetime")).toBeUndefined();
      expect(parseLocalISODateTime("")).toBeUndefined();
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
