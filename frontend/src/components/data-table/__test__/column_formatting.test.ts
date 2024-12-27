/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { applyFormat } from "../column-formatting/feature";
import {
  prettyScientificNumber,
  prettyEngineeringNumber,
} from "@/utils/numbers";

describe("applyFormat", () => {
  it("should return an empty string for null, undefined, or empty string values", () => {
    expect(applyFormat(null, "Date", "date")).toBe("");
    expect(applyFormat(undefined, "Date", "date")).toBe("");
    expect(applyFormat("", "Date", "date")).toBe("");
  });

  describe("date formatting", () => {
    it("should format date values correctly", () => {
      const date = "2023-10-01T12:00:00Z";
      expect(applyFormat(date, "Date", "date")).toBe("10/1/23");
      expect(applyFormat(date, "Datetime", "date")).toBe(
        "10/1/23, 12:00:00 PM UTC",
      );
    });

    it("should format time values correctly", () => {
      const time = "12:00:00Z";
      expect(applyFormat(time, "Time", "time")).toBe("12:00:00Z");
    });

    it("should format datetime values correctly", () => {
      const datetime = "2023-10-01T12:00:00Z";
      expect(applyFormat(datetime, "Datetime", "datetime")).toBe(
        "10/1/23, 12:00:00 PM UTC",
      );
    });
  });

  describe("number formatting", () => {
    it("should format number values correctly", () => {
      const number = "1234.567";
      expect(applyFormat(number, "Auto", "number")).toBe("1,234.57");
      expect(applyFormat(number, "Percent", "number")).toBe("123,456.7%");
      expect(applyFormat(number, "Scientific", "number")).toBe(
        prettyScientificNumber(1234.567),
      );
      expect(applyFormat(number, "Engineering", "number")).toBe(
        prettyEngineeringNumber(1234.567),
      );
      expect(applyFormat(number, "Integer", "number")).toBe("1,235");
    });
  });

  describe("string formatting", () => {
    it("should format string values correctly", () => {
      const str = "hello world";
      expect(applyFormat(str, "Uppercase", "string")).toBe("HELLO WORLD");
      expect(applyFormat(str, "Lowercase", "string")).toBe("hello world");
      expect(applyFormat(str, "Capitalize", "string")).toBe("Hello world");
      expect(applyFormat(str, "Title", "string")).toBe("Hello World");
    });
  });

  describe("boolean formatting", () => {
    it("should format boolean values correctly", () => {
      expect(applyFormat(true, "Yes/No", "boolean")).toBe("Yes");
      expect(applyFormat(false, "Yes/No", "boolean")).toBe("No");
      expect(applyFormat(true, "On/Off", "boolean")).toBe("On");
      expect(applyFormat(false, "On/Off", "boolean")).toBe("Off");
    });
  });

  it("should return the original value for unknown data types or formats", () => {
    expect(applyFormat("some value", "Auto", "unknown")).toBe("some value");
    expect(applyFormat(123, "Auto", "unknown")).toBe(123);
  });
});
