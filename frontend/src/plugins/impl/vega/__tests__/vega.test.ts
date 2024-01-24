/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import {
  ZERO_WIDTH_SPACE,
  uniquifyColumnNames,
  vegaLoadData,
  vegaLoader,
} from "../loader";

describe("vega loader", () => {
  it("should parse csv data", async () => {
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

  it("should parse csv data with NaN", async () => {
    const csvData = `
user,age
Alice,30.0
Bob,NaN
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const data = await vegaLoadData(csvData, { type: "csv", parse: "auto" });

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "age": "30.0",
          "user": "Alice",
        },
        {
          "age": "NaN",
          "user": "Bob",
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
