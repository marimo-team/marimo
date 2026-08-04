/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, test } from "vitest";
import {
  isPath,
  prefixPath,
  type PathPlaceholder,
  unprefixPath,
} from "../paths";

describe("paths", () => {
  test("isPath", () => {
    expect(isPath("path:/etc/secrets/key.json")).toBe(true);
    expect(isPath("path:")).toBe(true);
    expect(isPath("/etc/secrets/key.json")).toBe(false);
    expect(isPath("env:MY_SECRET")).toBe(false);
    expect(isPath("")).toBe(false);
    expect(isPath(null)).toBe(false);
    expect(isPath(undefined)).toBe(false);
    expect(isPath(123)).toBe(false);
  });

  test("prefixPath", () => {
    expect(prefixPath("/etc/secrets/key.json")).toBe(
      "path:/etc/secrets/key.json",
    );
    expect(prefixPath("")).toBe("path:");
  });

  test("unprefixPath", () => {
    expect(unprefixPath("path:/etc/secrets/key.json" as PathPlaceholder)).toBe(
      "/etc/secrets/key.json",
    );
    expect(unprefixPath("path:" as PathPlaceholder)).toBe("");
    // Only strips the leading prefix — path may itself contain "path:".
    expect(unprefixPath("path:/tmp/path:weird.json" as PathPlaceholder)).toBe(
      "/tmp/path:weird.json",
    );
  });
});
