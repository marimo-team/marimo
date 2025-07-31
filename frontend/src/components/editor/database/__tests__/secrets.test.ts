/* Copyright 2024 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  displaySecret,
  isSecret,
  prefixSecret,
  type SecretPlaceholder,
  unprefixSecret,
} from "../secrets";

describe("secrets", () => {
  test("displaySecret", () => {
    expect(displaySecret("env:mySecret")).toBe("env:mySecret");
    expect(displaySecret("regular-value")).toBe("regular-value");
    expect(displaySecret("")).toBe("");
  });

  test("isSecret", () => {
    expect(isSecret("env:mySecret")).toBe(true);
    expect(isSecret("regular-value")).toBe(false);
    expect(isSecret("")).toBe(false);
    expect(isSecret(null)).toBe(false);
    expect(isSecret(undefined)).toBe(false);
    expect(isSecret(123)).toBe(false);
  });

  test("prefixSecret", () => {
    expect(prefixSecret("mySecret")).toBe("env:mySecret");
    expect(prefixSecret("")).toBe("env:");
  });

  test("unprefixSecret", () => {
    expect(unprefixSecret("env:mySecret" as SecretPlaceholder)).toBe(
      "mySecret",
    );
    expect(unprefixSecret("env:" as SecretPlaceholder)).toBe("");
  });
});
