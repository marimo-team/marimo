/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, it, vi } from "vitest";
import {
  vegaLoadData,
  vegaLoader,
  exportedForTesting,
  parseCsvData,
} from "../loader";
import { DATA_TYPES } from "@/core/kernel/messages";

const { ZERO_WIDTH_SPACE, replacePeriodsInColumnNames, uniquifyColumnNames } =
  exportedForTesting;

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
          "active": 2023-08-14T19:28:47.000Z,
          "id": 1994308,
          "username": "akshayka",
        },
        {
          "active": 2023-08-14T21:30:17.000Z,
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

  it.each(DATA_TYPES)("should handle %s data-type", async (type) => {
    const csvData = "name,value_column\nAlice,1";
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const result = await vegaLoadData(csvData, {
      type: "csv",
      parse: { value_column: type },
    });
    expect(result.length).toEqual(1);
  });

  it("should parse csv data with out of bound integers", async () => {
    const csvData = "id\n912312851340981241284";

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));
    const data = await vegaLoadData(
      csvData,
      { type: "csv", parse: "auto" },
      { handleBigIntAndNumberLike: true },
    );
    expect(data).toMatchInlineSnapshot(`
      [
        {
          "id": 912312851340981241284n,
        },
      ]
    `);

    const dataWithoutFlag = await vegaLoadData(
      csvData,
      { type: "csv" },
      { handleBigIntAndNumberLike: false },
    );
    expect(dataWithoutFlag).toMatchInlineSnapshot(`
      [
        {
          "id": 912312851340981300000,
        },
      ]
    `);
  });

  it("should handle when there is no format given", async () => {
    const csvData = "id\n912312851340981241284";
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));
    const format = undefined;
    const data = await vegaLoadData(csvData, format, {
      handleBigIntAndNumberLike: true,
    });
    expect(data).toMatchInlineSnapshot(`
      [
        {
          "id": 912312851340981241284n,
        },
      ]
    `);

    const jsonData = `[{"id": "912312851340981241284"}]`;
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(jsonData));
    const data2 = await vegaLoadData(jsonData, format);
    expect(data2).toMatchInlineSnapshot(`
      [
        {
          "id": "912312851340981241284",
        },
      ]
    `);
  });

  it("should parse csv data with boolean values", async () => {
    const csvData = `
is_active,username
True,user1
False,user2
true,user3
false,user4
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const data = await vegaLoadData(csvData, { type: "csv", parse: "auto" });

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "is_active": "True",
          "username": "user1",
        },
        {
          "is_active": "False",
          "username": "user2",
        },
        {
          "is_active": "true",
          "username": "user3",
        },
        {
          "is_active": "false",
          "username": "user4",
        },
      ]
    `);
  });

  it("should handle inf and -inf values", async () => {
    const csvData = `
value,name
inf,positive_infinity
-inf,negative_infinity
100,regular_number
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const data = await vegaLoadData(csvData, { type: "csv", parse: "auto" });

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "name": "positive_infinity",
          "value": "inf",
        },
        {
          "name": "negative_infinity",
          "value": "-inf",
        },
        {
          "name": "regular_number",
          "value": "100",
        },
      ]
    `);
  });

  it("should handle BigInt values with and without the handleBigInt option", async () => {
    const csvData = `
id,name
9007199254740991,max_safe_integer
9007199254740992,above_max_safe_integer
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const dataWithBigInt = await vegaLoadData(
      csvData,
      { type: "csv", parse: "auto" },
      { handleBigIntAndNumberLike: true },
    );

    expect(dataWithBigInt).toMatchInlineSnapshot(`
      [
        {
          "id": 9007199254740991,
          "name": "max_safe_integer",
        },
        {
          "id": 9007199254740992n,
          "name": "above_max_safe_integer",
        },
      ]
    `);

    const dataWithoutBigInt = await vegaLoadData(
      csvData,
      { type: "csv", parse: "auto" },
      { handleBigIntAndNumberLike: false },
    );

    expect(dataWithoutBigInt).toMatchInlineSnapshot(`
      [
        {
          "id": 9007199254740991,
          "name": "max_safe_integer",
        },
        {
          "id": 9007199254740992,
          "name": "above_max_safe_integer",
        },
      ]
    `);
  });

  it("should handle JSON data", async () => {
    const jsonData = JSON.stringify([
      { name: "Alice", age: 30 },
      { name: "Bob", age: 25 },
    ]);

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(jsonData));

    const data = await vegaLoadData(jsonData, { type: "json" });

    expect(data).toMatchInlineSnapshot(`
      [
        {
          "age": 30,
          "name": "Alice",
        },
        {
          "age": 25,
          "name": "Bob",
        },
      ]
    `);
  });

  it("should handle the replacePeriod option", async () => {
    const csvData = `
user.name,user.age
Alice.Smith,30
Bob.Jones,25
`.trim();

    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));

    const dataWithReplacePeriod = await vegaLoadData(
      csvData,
      { type: "csv", parse: "auto" },
      { replacePeriod: true },
    );

    expect(dataWithReplacePeriod).toMatchInlineSnapshot(`
      [
        {
          "user․age": 30,
          "user․name": "Alice.Smith",
        },
        {
          "user․age": 25,
          "user․name": "Bob.Jones",
        },
      ]
    `);

    const dataWithoutReplacePeriod = await vegaLoadData(
      csvData,
      { type: "csv", parse: "auto" },
      { replacePeriod: false },
    );

    expect(dataWithoutReplacePeriod).toMatchInlineSnapshot(`
      [
        {
          "user.age": 30,
          "user.name": "Alice.Smith",
        },
        {
          "user.age": 25,
          "user.name": "Bob.Jones",
        },
      ]
    `);
  });

  it("should handle null values", async () => {
    const csvData = "name,age\nAlice,30\nBob,null";
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));
    const data = await vegaLoadData(csvData, {
      type: "csv",
      parse: { age: "number", name: "string" },
    });
    expect(data).toMatchInlineSnapshot(`
      [
        {
          "age": 30,
          "name": "Alice",
        },
        {
          "age": NaN,
          "name": "Bob",
        },
      ]
    `);
  });

  it("should handle empty dates", async () => {
    const csvData = "name,created_at\nAlice,2024-01-01T00:00:00Z\nBob,";
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));
    const data = await vegaLoadData(csvData, {
      type: "csv",
      parse: { created_at: "date", name: "string" },
    });
    expect(data).toMatchInlineSnapshot(`
      [
        {
          "created_at": 2024-01-01T00:00:00.000Z,
          "name": "Alice",
        },
        {
          "created_at": "",
          "name": "Bob",
        },
      ]
    `);
  });

  it("should handle NaN numbers, when handleBigInt is true", async () => {
    const csvData = 'name,amount,id\nAlice,,"#1"\nBob,"$2,000","#2"';
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));
    const data = await vegaLoadData(
      csvData,
      {
        type: "csv",
        parse: { amount: "number", name: "string", id: "integer" },
      },
      { handleBigIntAndNumberLike: true },
    );
    expect(data).toMatchInlineSnapshot(`
      [
        {
          "amount": null,
          "id": "#1",
          "name": "Alice",
        },
        {
          "amount": "$2,000",
          "id": "#2",
          "name": "Bob",
        },
      ]
    `);
  });

  it("should handle NaN numbers, when handleBigInt is false", async () => {
    const csvData = 'name,amount,id\nAlice,,"#1"\nBob,"$2,000","#2"';
    vi.spyOn(vegaLoader, "load").mockReturnValue(Promise.resolve(csvData));
    const data = await vegaLoadData(
      csvData,
      {
        type: "csv",
        parse: { amount: "number", name: "string", id: "integer" },
      },
      { handleBigIntAndNumberLike: false },
    );
    expect(data).toMatchInlineSnapshot(`
      [
        {
          "amount": null,
          "id": NaN,
          "name": "Alice",
        },
        {
          "amount": NaN,
          "id": NaN,
          "name": "Bob",
        },
      ]
    `);
  });

  it.skip("should handle arrow files", async () => {
    // Create a small arrow file with schema and one empty record batch
    const arrowData = new Uint8Array([
      0x41,
      0x52,
      0x52,
      0x4f,
      0x57,
      0x31,
      0x00,
      0x00, // "ARROW1\0\0"
    ]);
    global.fetch = vi.fn().mockResolvedValue({
      arrayBuffer: () => Promise.resolve(arrowData.buffer),
    });
    const data = await vegaLoadData(
      "data.arrow",
      {
        type: "arrow",
      },
      { handleBigIntAndNumberLike: true },
    );
    expect(data).toBe([]);
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

describe("replacePeriodsInColumnNames", () => {
  it("should handle empty cases", () => {
    expect(replacePeriodsInColumnNames("")).toBe("");
    expect(replacePeriodsInColumnNames(" ")).toBe(" ");
    expect(replacePeriodsInColumnNames("\n")).toBe("\n");
  });

  it("should return the same header if no periods exist", () => {
    const csvData = "Name,Age,Location\nAlice,30,New York";
    const result = replacePeriodsInColumnNames(csvData);
    expect(result).toBe(csvData);
  });

  it("should replace periods in headers", () => {
    const csvData =
      "user.name,user.age,user.location\nAlice,30.1,New York\nBob,30.5,New York";
    const expectedResult =
      "user․name,user․age,user․location\nAlice,30.1,New York\nBob,30.5,New York";
    const result = replacePeriodsInColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });

  it("should not replace periods in non-headers", () => {
    const csvData = "Name,Age,Location\nAlice,30.1,New York\nBob,30.5,New York";
    const expectedResult =
      "Name,Age,Location\nAlice,30.1,New York\nBob,30.5,New York";
    const result = replacePeriodsInColumnNames(csvData);
    expect(result).toBe(expectedResult);
  });
});

describe("parseCsvData", () => {
  it("should parse CSV data with and without handleBigInt option", () => {
    const csvData = `
id,name,value
9007199254740992,big_int,1.5
100,regular,2.0
`.trim();

    const dataWithBigInt = parseCsvData(csvData, true);
    const dataWithoutBigInt = parseCsvData(csvData, false);

    expect(dataWithBigInt).toMatchInlineSnapshot(`
      [
        {
          "id": 9007199254740992n,
          "name": "big_int",
          "value": 1.5,
        },
        {
          "id": 100,
          "name": "regular",
          "value": 2,
        },
      ]
    `);

    expect(dataWithoutBigInt).toMatchInlineSnapshot(`
      [
        {
          "id": 9007199254740992,
          "name": "big_int",
          "value": 1.5,
        },
        {
          "id": 100,
          "name": "regular",
          "value": 2,
        },
      ]
    `);
  });
});
