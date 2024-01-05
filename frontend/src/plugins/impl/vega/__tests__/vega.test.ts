/* Copyright 2023 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import { uniquifyColumnNames, vegaLoadData, vegaLoader } from "../loader";

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
    const expectedResult = "Name,Age,Location,Name_1\nAlice,30,New York,Bob";
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });

  it("should uniquify headers with all duplicates", () => {
    const csvData = "Name,Name,Name,Name\nAlice,Bob,Charlie,David";
    const expectedResult = "Name,Name_1,Name_2,Name_3\nAlice,Bob,Charlie,David";
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });

  it("should handle empty column names", () => {
    const csvData = "Name,,Location,Name\nAlice,30,New York,Bob";
    const expectedResult = "Name,,Location,Name_1\nAlice,30,New York,Bob";
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
    const expectedResult =
      '"Name,Name",Name,Name_1,Name_2\nAlice,Bob,Charlie,David';
    const result = uniquifyColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });
});
