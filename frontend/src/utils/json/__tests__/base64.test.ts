/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  type Base64String,
  type ByteString,
  base64ToDataURL,
  byteStringToBinary,
  type DataURLString,
  deserializeBase64,
  extractBase64FromDataURL,
  isDataURLString,
  type JsonString,
  typedAtob,
  typedBtoa,
} from "../base64";

describe("base64Utils", () => {
  const testData = {
    name: "marimo inc",
    type: "company",
  };

  const expectedBase64 =
    "JTdCJTIybmFtZSUyMiUzQSUyMm1hcmltbyUyMGluYyUyMiUyQyUyMnR5cGUlMjIlM0ElMjJjb21wYW55JTIyJTdE" as Base64String<
      JsonString<typeof testData>
    >;

  test("serializeJsonToBase64 should correctly encode JSON to Base64", () => {
    const base64Encoded = serializeJsonToBase64(testData);
    expect(base64Encoded).toBe(expectedBase64);
  });

  test("deserializeBase64ToJson should correctly decode Base64 to JSON", () => {
    const jsonDecoded = deserializeBase64(expectedBase64);
    expect(JSON.parse(jsonDecoded)).toEqual(testData);
  });

  test("serializeJsonToBase64 and deserializeBase64ToJson should be reversible", () => {
    const base64Encoded = serializeJsonToBase64(testData);
    const jsonDecoded = deserializeBase64(base64Encoded);
    expect(JSON.parse(jsonDecoded)).toEqual(testData);
  });

  test("base64ToDataURL should create proper data URL", () => {
    const base64 = "SGVsbG8=" as Base64String;
    const result = base64ToDataURL(base64, "text/plain");
    expect(result).toBe("data:text/plain;base64,SGVsbG8=");
  });

  test("typedAtob and typedBtoa should be reversible", () => {
    const original = "hello world" as ByteString;
    const encoded = typedBtoa(original);
    const decoded = typedAtob(encoded);
    expect(decoded).toBe(original);
  });

  test.each([
    ["data:text/plain;base64,SGVsbG8=", true],
    ["data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA", true],
    ["not-a-data-url", false],
    ["base64,SGVsbG8=", false],
  ])("isDataURLString(%s) should return %s", (input, expected) => {
    expect(isDataURLString(input)).toBe(expected);
  });

  test("isDataURLString should reject data URLs without base64", () => {
    expect(isDataURLString("data:text/plain,hello")).toBe(false);
    expect(isDataURLString("data:text/plain;charset=utf-8,hello")).toBe(false);
  });

  test.each([
    ["data:text/plain;base64,SGVsbG8=", "SGVsbG8="],
    [
      "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgA",
      "iVBORw0KGgoAAAANSUhEUgA",
    ],
    ["data:application/json;base64,", ""],
    ["data:text/html;charset=utf-8;base64,PGh0bWw+", "PGh0bWw+"],
  ])("extractBase64FromDataURL(%s) should return %s", (dataUrl, expected) => {
    expect(extractBase64FromDataURL(dataUrl as DataURLString)).toBe(expected);
  });

  test("byteStringToBinary should convert to Uint8Array", () => {
    const bytes = "ABC" as ByteString;
    const result = byteStringToBinary(bytes);
    expect(result).toEqual(new Uint8Array([65, 66, 67]));
  });

  test("byteStringToBinary should handle empty string", () => {
    const bytes = "" as ByteString;
    const result = byteStringToBinary(bytes);
    expect(result).toEqual(new Uint8Array([]));
  });
});

// Serialization: JSON to Base64
function serializeJsonToBase64<T>(jsonObject: T) {
  const jsonString = JSON.stringify(jsonObject);
  return btoa(encodeURIComponent(jsonString)) as Base64String<JsonString<T>>;
}
