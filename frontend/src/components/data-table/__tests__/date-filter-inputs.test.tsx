/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parsePastedRange } from "../date-filter-inputs";
import { dateToISODate } from "../filters";

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
    expect(result && dateToISODate(result.min)).toBe("2026-02-01");
    expect(result && dateToISODate(result.max)).toBe("2026-04-01");
  });

  it("returns a degenerate range for a single pasted date", () => {
    const result = parsePastedRange("date", "2026-03-15");
    expect(result).toBeDefined();
    expect(result && dateToISODate(result.min)).toBe("2026-03-15");
    expect(result && dateToISODate(result.max)).toBe("2026-03-15");
  });

  it("returns undefined for unparsable input", () => {
    expect(parsePastedRange("date", "Sunday and Monday")).toBeUndefined();
    expect(parsePastedRange("date", "not a date")).toBeUndefined();
  });
});
