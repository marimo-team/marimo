/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import {
  prettyEngineeringNumber,
  prettyScientificNumber,
} from "@/utils/numbers";
import { applyFormat } from "../column-formatting/feature";

const locale = "en-US";

describe("applyFormat", () => {
  it("should return an empty string for null, undefined, or empty string values", () => {
    expect(
      applyFormat(null, { format: "Date", dataType: "date", locale }),
    ).toBe("");
    expect(
      applyFormat(undefined, { format: "Date", dataType: "date", locale }),
    ).toBe("");
    expect(applyFormat("", { format: "Date", dataType: "date", locale })).toBe(
      "",
    );
  });

  describe("date formatting", () => {
    it("should format date values correctly", () => {
      const date = "2023-10-01T12:00:00Z";
      expect(
        applyFormat(date, { format: "Date", dataType: "date", locale }),
      ).toBe("10/1/23");
      expect(
        applyFormat(date, { format: "Datetime", dataType: "date", locale }),
      ).toBe("10/1/23, 12:00:00 PM UTC");
    });

    it("should format time values correctly", () => {
      const time = "12:00:00Z";
      expect(
        applyFormat(time, { format: "Time", dataType: "time", locale }),
      ).toBe("12:00:00Z");
    });

    it("should format datetime values correctly", () => {
      const datetime = "2023-10-01T12:00:00Z";
      expect(
        applyFormat(datetime, {
          locale,
          format: "Datetime",
          dataType: "datetime",
        }),
      ).toBe("10/1/23, 12:00:00 PM UTC");
    });
  });

  describe("number formatting", () => {
    it("should format number values correctly", () => {
      const number = "1234.567";
      expect(
        applyFormat(number, { format: "Auto", dataType: "number", locale }),
      ).toBe("1,234.57");
      expect(
        applyFormat(number, { format: "Percent", dataType: "number", locale }),
      ).toBe("123,456.7%");
      expect(
        applyFormat(number, {
          locale,
          format: "Scientific",
          dataType: "number",
        }),
      ).toBe(prettyScientificNumber(1234.567, { shouldRound: true, locale }));
      expect(
        applyFormat(number, {
          format: "Engineering",
          dataType: "number",
          locale,
        }),
      ).toBe(prettyEngineeringNumber(1234.567, locale));
      expect(
        applyFormat(number, { format: "Integer", dataType: "number", locale }),
      ).toBe("1,235");
    });
  });

  describe("string formatting", () => {
    it("should format string values correctly", () => {
      const str = "hello world";
      expect(
        applyFormat(str, { format: "Uppercase", dataType: "string", locale }),
      ).toBe("HELLO WORLD");
      expect(
        applyFormat(str, { format: "Lowercase", dataType: "string", locale }),
      ).toBe("hello world");
      expect(
        applyFormat(str, { format: "Capitalize", dataType: "string", locale }),
      ).toBe("Hello world");
      expect(
        applyFormat(str, { format: "Title", dataType: "string", locale }),
      ).toBe("Hello World");
    });
  });

  describe("boolean formatting", () => {
    it("should format boolean values correctly", () => {
      expect(
        applyFormat(true, { format: "Yes/No", dataType: "boolean", locale }),
      ).toBe("Yes");
      expect(
        applyFormat(false, { format: "Yes/No", dataType: "boolean", locale }),
      ).toBe("No");
      expect(
        applyFormat(true, { format: "On/Off", dataType: "boolean", locale }),
      ).toBe("On");
      expect(
        applyFormat(false, { format: "On/Off", dataType: "boolean", locale }),
      ).toBe("Off");
    });
  });

  it("should return the original value for unknown data types or formats", () => {
    expect(
      applyFormat("some value", {
        format: "Auto",
        dataType: "unknown",
        locale,
      }),
    ).toBe("some value");
    expect(
      applyFormat(123, { format: "Auto", dataType: "unknown", locale }),
    ).toBe(123);
  });
});
