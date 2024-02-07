/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import {
  ZERO_WIDTH_SPACE,
  uniquifyColumnNames,
  vegaLoadData,
  vegaLoader,
} from "../loader";

describe("vega loader", () => {
  it("should parse csv data with dates", async () => {
    const csvData = `
active,username,id
2023-08-14T19:28:47Z,akshayka,1994308
2023-08-14T21:30:17Z,mscolnick,5108954
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const data = await vegaLoadData(csvData, { type: "csv", parse: "auto" });

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "active": "2023-08-14T19:28:47.000Z",
          "id": 1994308,
          "username": "akshayka",
        },
        {
          "active": "2023-08-14T21:30:17.000Z",
          "id": 5108954,
          "username": "mscolnick",
        },
      ]
    `);
  });

  it("should parse csv data with floats", async () => {
    const csvData = `
yield_error,yield_center
7.5522,32.4
6.9775,30.96667
3.9167,33.966665
11.9732,30.45
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const data = await vegaLoadData(csvData, { type: "csv", parse: "auto" });
    const dataWithoutParseAuto = await vegaLoadData(csvData, { type: "csv" });

    expect(data).toEqual(dataWithoutParseAuto);

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "yield_center": 32.4,
          "yield_error": 7.5522,
        },
        {
          "yield_center": 30.96667,
          "yield_error": 6.9775,
        },
        {
          "yield_center": 33.966665,
          "yield_error": 3.9167,
        },
        {
          "yield_center": 30.45,
          "yield_error": 11.9732,
        },
      ]
    `);
  });
});

describe("uniquifyColumnNames", () => {
  it("should handle empty cases", () => {
    expect(uniquifyColumnNames("")).toBe("");
    expect(uniquifyColumnNames(" ")).toBe(" ");
    expect(uniquifyColumnNames("\n")).toBe("\n");
  });

  it("should return the same header if no duplicates exist", () => {
    const csvData = "Name,Age,Location\nAlice,30,New York";
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(csvData);
  });

  it("should uniquify headers with some duplicates", () => {
    const csvData = "Name,Age,Location,Name\nAlice,30,New York,Bob";
    const expectedResult = `Name,Age,Location,Name${ZERO_WIDTH_SPACE}\nAlice,30,New York,Bob`;
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
    expect(result).not.toMatch(csvData);
  });

  it("should uniquify headers with all duplicates", () => {
    const csvData = "Name,Name,Name\nAlice,Bob,Charlie";
    const expectedResult = `Name,Name${ZERO_WIDTH_SPACE},Name${ZERO_WIDTH_SPACE}${ZERO_WIDTH_SPACE}\nAlice,Bob,Charlie`;
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });

  it("should handle empty column names", () => {
    const csvData = "Name,,Location,Name\nAlice,30,New York,Bob";
    const expectedResult = `Name,,Location,Name${ZERO_WIDTH_SPACE}\nAlice,30,New York,Bob`;
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });

  it("should handle special characters in column names", () => {
    const csvData = "Na!me,Na@me,Na#me,Na$me\nAlice,Bob,Charlie,David";
    const expectedResult = "Na!me,Na@me,Na#me,Na$me\nAlice,Bob,Charlie,David";
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });

  it("should handle commas in quoted column names", () => {
    const csvData = '"Name,Name",Name,Name,Name\nAlice,Bob,Charlie,David';
    const expectedResult = `"Name,Name",Name,Name${ZERO_WIDTH_SPACE},Name${ZERO_WIDTH_SPACE}${ZERO_WIDTH_SPACE}\nAlice,Bob,Charlie,David`;
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });
});
