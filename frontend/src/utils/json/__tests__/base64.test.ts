/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  type Base64String,
  deserializeBase64,
  type JsonString,
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
});

// Serialization: JSON to Base64
function serializeJsonToBase64<T>(jsonObject: T) {
  const jsonString = JSON.stringify(jsonObject);
  return btoa(encodeURIComponent(jsonString)) as Base64String<JsonString<T>>;
}
