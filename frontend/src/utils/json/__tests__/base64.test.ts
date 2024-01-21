/* Copyright 2024 Marimo. All rights reserved. */
import { expect, describe, test } from "vitest";
import {
  serializeJsonToBase64,
  deserializeBase64ToJson,
  Base64String,
} from "../base64";

describe("base64Utils", () => {
  const testData = {
    name: "marimo inc",
    type: "company",
  };

  const expectedBase64 =
    "JTdCJTIybmFtZSUyMiUzQSUyMm1hcmltbyUyMGluYyUyMiUyQyUyMnR5cGUlMjIlM0ElMjJjb21wYW55JTIyJTdE" as Base64String;

  test("serializeJsonToBase64 should correctly encode JSON to Base64", () => {
    const base64Encoded = serializeJsonToBase64(testData);
    expect(base64Encoded).toBe(expectedBase64);
  });

  test("deserializeBase64ToJson should correctly decode Base64 to JSON", () => {
    const jsonDecoded = deserializeBase64ToJson(expectedBase64);
    expect(jsonDecoded).toEqual(testData);
  });

  test("serializeJsonToBase64 and deserializeBase64ToJson should be reversible", () => {
    const base64Encoded = serializeJsonToBase64(testData);
    const jsonDecoded = deserializeBase64ToJson(base64Encoded);
    expect(jsonDecoded).toEqual(testData);
  });

  test("deserializeBase64ToJson should throw an error for invalid Base64 strings", () => {
    const invalidBase64 = "InvalidBase64String" as Base64String;
    expect(() => {
      deserializeBase64ToJson(invalidBase64);
    }).toThrow(SyntaxError);
  });
});
