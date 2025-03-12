/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, beforeAll, afterAll } from "vitest";
import { prettyDate, exactDateTime, timeAgo } from "../dates";

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
  });

  describe("exactDateTime", () => {
    it("formats date without milliseconds", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, false)).toBe("2023-05-15 12:00:00");
    });

    it("formats date with milliseconds", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, false)).toBe("2023-05-15 12:00:00.123");
    });

    it("formats date in UTC when renderInUTC is true", () => {
      const date = new Date("2023-05-15T12:00:00.000Z");
      expect(exactDateTime(date, true)).toBe("2023-05-15 12:00:00 UTC");
    });

    it("formats date with milliseconds in UTC when renderInUTC is true", () => {
      const date = new Date("2023-05-15T12:00:00.123Z");
      expect(exactDateTime(date, true)).toBe("2023-05-15 12:00:00.123 UTC");
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
});
