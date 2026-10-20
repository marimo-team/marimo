/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { dateToLocalISODate } from "@/utils/dates";
import { parsePastedDate, parsePastedRange } from "../date-filter-inputs";

describe("parsePastedDate", () => {
  it("parses a time-only string for the time filter type", () => {
    const result = parsePastedDate("time", "2:30 PM");
    expect(result).toEqual(new Date(1970, 0, 1, 14, 30));
  });

  it("parses a local ISO datetime for the datetime filter type", () => {
    const result = parsePastedDate("datetime", "2026-02-01T08:30:00");
    expect(result).toEqual(new Date(2026, 1, 1, 8, 30, 0));
  });

  it("falls back to the Date constructor for other formats", () => {
    const result = parsePastedDate("datetime", "Feb 1, 2026 08:30:00");
    expect(result).toBeDefined();
    expect(result?.getFullYear()).toBe(2026);
  });

  it("returns undefined for an empty or unparsable string", () => {
    expect(parsePastedDate("date", "")).toBeUndefined();
    expect(parsePastedDate("time", "not-a-time")).toBeUndefined();
  });
});

describe("parsePastedRange", () => {
  it.each([
    ["hyphen", "2026-02-01 - 2026-04-01"],
    ["en dash", "2026-02-01 – 2026-04-01"],
    ["em dash", "2026-02-01 — 2026-04-01"],
    ["to", "2026-02-01 to 2026-04-01"],
    ["TO (uppercase)", "2026-02-01 TO 2026-04-01"],
    ["and", "2026-02-01 and 2026-04-01"],
    ["AND (uppercase)", "2026-02-01 AND 2026-04-01"],
  ])("splits a date range pasted with %s separator", (_, text) => {
    const result = parsePastedRange("date", text);
    expect(result).toBeDefined();
    expect(result && dateToLocalISODate(result.min)).toBe("2026-02-01");
    expect(result && dateToLocalISODate(result.max)).toBe("2026-04-01");
  });

  it("returns a degenerate range for a single pasted date", () => {
    const result = parsePastedRange("date", "2026-03-15");
    expect(result).toBeDefined();
    expect(result && dateToLocalISODate(result.min)).toBe("2026-03-15");
    expect(result && dateToLocalISODate(result.max)).toBe("2026-03-15");
  });

  it("returns undefined for unparsable input", () => {
    expect(parsePastedRange("date", "Sunday and Monday")).toBeUndefined();
    expect(parsePastedRange("date", "not a date")).toBeUndefined();
  });
});
