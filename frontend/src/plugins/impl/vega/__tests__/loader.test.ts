/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { parseCsvData } from "../loader";

interface VersionData {
  Version: string;
  Days: string | number;
}

interface DateData {
  Date: Date;
  Value: string | number;
}

describe("DATE_MIDDLEWARE", () => {
  it("should not parse version strings as dates", () => {
    // Given a CSV with version strings
    const csv = "Version,Days\n1.1.1,3\n2.2.2,4";

    // When parsing the CSV
    const data = parseCsvData(csv, false) as VersionData[];

    // Then version strings should remain as strings
    expect(typeof data[0].Version).toBe("string");
    expect(data[0].Version).toBe("1.1.1");
    expect(data[1].Version).toBe("2.2.2");
  });

  it("should parse valid ISO date strings as dates", () => {
    // Given a CSV with ISO date strings
    const csv =
      "Date,Value\n2024-03-14T12:00:00Z,100\n2024-03-15T12:00:00Z,200";

    // When parsing the CSV
    const data = parseCsvData(csv, false) as DateData[];

    // Then dates should be parsed as Date objects
    expect(data[0].Date instanceof Date).toBe(true);
    expect(data[1].Date instanceof Date).toBe(true);
  });

  it("should parse valid dates without times as dates", () => {
    // Given a CSV with date strings without times
    const csv = "Date,Value\n2024-03-14,100\n2024-02-29,200";

    // When parsing the CSV
    const data = parseCsvData(csv, false) as DateData[];

    // Then dates should be parsed as Date objects
    expect(data[0].Date instanceof Date).toBe(true);
    expect(data[1].Date instanceof Date).toBe(true);
    // And should preserve the correct date
    expect(data[0].Date.toISOString().split("T")[0]).toBe("2024-03-14");
    expect(data[1].Date.toISOString().split("T")[0]).toBe("2024-02-29");
  });

  it("should not parse invalid dates that match YYYY-MM-DD format", () => {
    // Given a CSV with invalid dates that match the format
    const csv = "Date,Value\n2024-13-45,100\n2024-02-30,200";

    // When parsing the CSV
    const data = parseCsvData(csv, false) as Array<{
      Date: string;
      Value: number;
    }>;

    // Then invalid dates should remain as strings
    expect(typeof data[0].Date).toBe("string");
    expect(data[0].Date).toBe("2024-13-45");
    expect(typeof data[1].Date).toBe("string");
    expect(data[1].Date).toBe("2024-02-30");
  });
});
