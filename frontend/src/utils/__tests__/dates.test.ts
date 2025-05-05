/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, beforeAll, afterAll } from "vitest";
import { prettyDate, exactDateTime, timeAgo, getShortTimeZone } from "../dates";

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
      expect(prettyDate(null, "date")).toBe("");
      expect(prettyDate(undefined, "date")).toBe("");
    });

    it("formats date correctly", () => {
      const date = new Date("2023-05-15T12:00:00Z");
      // Using a regex to match the pattern since exact format may vary by locale
      expect(prettyDate(date.toISOString(), "date")).toMatch(/May 15, 2023/);
    });

    it("formats datetime correctly", () => {
      const date = new Date("2023-05-15T12:00:00Z");
      expect(prettyDate(date.toISOString(), "datetime")).toMatch(
        /May 15, 2023/,
      );
    });

    it("handles errors gracefully", () => {
      expect(prettyDate("invalid-date", "date")).toBe("Invalid Date");
    });

    it("handles numeric timestamp input", () => {
      const timestamp = 1_684_152_000_000; // 2023-05-15T12:00:00Z in milliseconds
      expect(prettyDate(timestamp, "date")).toMatch(/May 15, 2023/);
    });

    it("preserves timezone for datetime type", () => {
      // This date is in winter time to avoid daylight saving time issues
      const date = new Date("2023-01-15T15:30:00Z");
      expect(prettyDate(date.toISOString(), "datetime")).toMatch(
        /Jan 15, 2023/,
      );
    });

    it("drops timezone for date type by using UTC", () => {
      // Create a date that would be different days in different timezones
      const date = new Date("2023-05-15T23:30:00Z"); // Late in the day UTC
      expect(prettyDate(date.toISOString(), "date")).toMatch(/May 15, 2023/);
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
        expect(prettyDate(date.toISOString(), "date")).toBe("15 mai 2023");
      });
    });
  });

  describe("exactDateTime", () => {
    it("formats date without milliseconds", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, undefined)).toBe("2023-05-15 12:00:00");
    });

    it("formats date with milliseconds", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, undefined)).toBe("2023-05-15 12:00:00.123");
    });

    it("formats date in UTC when renderInUTC is true", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, "UTC")).toBe("2023-05-15 12:00:00 UTC");
    });

    it("formats date with milliseconds in UTC when renderInUTC is true", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, "UTC")).toBe("2023-05-15 12:00:00.123 UTC");
    });

    it("formats date in America/New_York timezone", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, "America/New_York")).toBe(
        "2023-05-15 08:00:00 EDT",
      );
    });

    it("formats date with milliseconds in America/New_York timezone", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, "America/New_York")).toBe(
        "2023-05-15 08:00:00.123 EDT",
      );
    });
  });

  describe("timeAgo", () => {
    it("returns empty string for null, undefined, or 0", () => {
      expect(timeAgo(null)).toBe("");
      expect(timeAgo(undefined)).toBe("");
      expect(timeAgo(0)).toBe("");
    });

    it("formats today's date correctly", () => {
      const today = new Date();
      const result = timeAgo(today.toISOString());
      expect(result).toMatch(/Today at/);
    });

    it("formats yesterday's date correctly", () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const result = timeAgo(yesterday.toISOString());
      expect(result).toMatch(/Yesterday at/);
    });

    it("formats older dates correctly", () => {
      const oldDate = new Date("2020-01-01T12:00:00Z");
      const result = timeAgo(oldDate.toISOString());
      expect(result).toMatch(/Jan 1, 2020 at/);
    });

    it("handles errors gracefully", () => {
      expect(timeAgo("invalid-date")).toBe("Invalid Date at Invalid Date");
    });
  });

  describe("getShortTimeZone", () => {
    it("returns the short timezone", () => {
      expect(getShortTimeZone("America/New_York")).toBeOneOf(["EDT", "EST"]);
    });

    it("handles errors gracefully", () => {
      expect(getShortTimeZone("MarimoLand")).toBe("MarimoLand");
    });
  });
});
