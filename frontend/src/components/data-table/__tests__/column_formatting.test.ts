/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  prettyEngineeringNumber,
  prettyScientificNumber,
} from "@/utils/numbers";
import { applyFormat } from "../column-formatting/feature";

describe("applyFormat", () => {
  it("should return an empty string for null, undefined, or empty string values", () => {
    expect(applyFormat(null, { format: "Date", dataType: "date" })).toBe("");
    expect(applyFormat(undefined, { format: "Date", dataType: "date" })).toBe(
      "",
    );
    expect(applyFormat("", { format: "Date", dataType: "date" })).toBe("");
  });

  describe("date formatting", () => {
    it("should format date values correctly", () => {
      const date = "2023-10-01T12:00:00Z";
      expect(applyFormat(date, { format: "Date", dataType: "date" })).toBe(
        "10/1/23",
      );
      expect(applyFormat(date, { format: "Datetime", dataType: "date" })).toBe(
        "10/1/23, 12:00:00 PM UTC",
      );
    });

    it("should format time values correctly", () => {
      const time = "12:00:00Z";
      expect(applyFormat(time, { format: "Time", dataType: "time" })).toBe(
        "12:00:00Z",
      );
    });

    it("should format datetime values correctly", () => {
      const datetime = "2023-10-01T12:00:00Z";
      expect(
        applyFormat(datetime, {
          format: "Datetime",
          dataType: "datetime",
        }),
      ).toBe("10/1/23, 12:00:00 PM UTC");
    });
  });

  describe("number formatting", () => {
    it("should format number values correctly", () => {
      const number = "1234.567";
      expect(applyFormat(number, { format: "Auto", dataType: "number" })).toBe(
        "1,234.57",
      );
      expect(
        applyFormat(number, { format: "Percent", dataType: "number" }),
      ).toBe("123,456.7%");
      expect(
        applyFormat(number, {
          format: "Scientific",
          dataType: "number",
        }),
      ).toBe(prettyScientificNumber(1234.567, { shouldRound: true }));
      expect(
        applyFormat(number, {
          format: "Engineering",
          dataType: "number",
        }),
      ).toBe(prettyEngineeringNumber(1234.567));
      expect(
        applyFormat(number, { format: "Integer", dataType: "number" }),
      ).toBe("1,235");
    });
  });

  describe("string formatting", () => {
    it("should format string values correctly", () => {
      const str = "hello world";
      expect(
        applyFormat(str, { format: "Uppercase", dataType: "string" }),
      ).toBe("HELLO WORLD");
      expect(
        applyFormat(str, { format: "Lowercase", dataType: "string" }),
      ).toBe("hello world");
      expect(
        applyFormat(str, { format: "Capitalize", dataType: "string" }),
      ).toBe("Hello world");
      expect(applyFormat(str, { format: "Title", dataType: "string" })).toBe(
        "Hello World",
      );
    });
  });

  describe("boolean formatting", () => {
    it("should format boolean values correctly", () => {
      expect(applyFormat(true, { format: "Yes/No", dataType: "boolean" })).toBe(
        "Yes",
      );
      expect(
        applyFormat(false, { format: "Yes/No", dataType: "boolean" }),
      ).toBe("No");
      expect(applyFormat(true, { format: "On/Off", dataType: "boolean" })).toBe(
        "On",
      );
      expect(
        applyFormat(false, { format: "On/Off", dataType: "boolean" }),
      ).toBe("Off");
    });
  });

  it("should return the original value for unknown data types or formats", () => {
    expect(
      applyFormat("some value", { format: "Auto", dataType: "unknown" }),
    ).toBe("some value");
    expect(applyFormat(123, { format: "Auto", dataType: "unknown" })).toBe(123);
  });
});
