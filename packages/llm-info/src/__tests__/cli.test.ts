/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { parseCliArgs } from "../cli.ts";

describe("parseCliArgs / mode", () => {
  it("defaults to append", () => {
    expect(parseCliArgs([]).mode).toBe("append");
  });

  it.each([
    ["--replace"],
    ["-r"],
    ["--mode=replace"],
    // Regression: the two-token form used to silently fall through to append.
    ["--mode", "replace"],
  ])("recognises %j as replace mode", (...flags: string[]) => {
    expect(parseCliArgs(flags).mode).toBe("replace");
  });

  it("accepts --mode=append explicitly", () => {
    expect(parseCliArgs(["--mode=append"]).mode).toBe("append");
    expect(parseCliArgs(["--mode", "append"]).mode).toBe("append");
  });

  it("rejects unknown --mode values", () => {
    expect(() => parseCliArgs(["--mode", "wipe"])).toThrow(
      /Unknown --mode value/,
    );
  });
});

describe("parseCliArgs / max-per-provider", () => {
  it("returns undefined when not provided", () => {
    expect(parseCliArgs([]).maxPerProvider).toBeUndefined();
  });

  it.each([
    ["--max-per-provider=5", 5],
    ["--max=3", 3],
    ["-n=7", 7],
  ])("parses %s as %i", (flag, expected) => {
    expect(parseCliArgs([flag]).maxPerProvider).toBe(expected);
  });

  it("parses the two-token form `-n 4`", () => {
    expect(parseCliArgs(["-n", "4"]).maxPerProvider).toBe(4);
  });

  it("ignores non-positive / non-numeric values", () => {
    expect(parseCliArgs(["-n", "0"]).maxPerProvider).toBeUndefined();
    expect(parseCliArgs(["-n", "abc"]).maxPerProvider).toBeUndefined();
  });
});

describe("parseCliArgs / providers", () => {
  it("returns undefined when not provided", () => {
    expect(parseCliArgs([]).providers).toBeUndefined();
  });

  it("parses a single known provider", () => {
    expect(parseCliArgs(["--provider=anthropic"]).providers).toEqual([
      "anthropic",
    ]);
  });

  it("parses a comma-separated list and trims whitespace", () => {
    expect(parseCliArgs(["-p", "anthropic, openai ,google"]).providers).toEqual(
      ["anthropic", "openai", "google"],
    );
  });

  it("warns about unknown providers but keeps the known ones", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(parseCliArgs(["-p", "anthropic,bogus"]).providers).toEqual([
        "anthropic",
      ]);
      expect(warn).toHaveBeenCalled();
    } finally {
      warn.mockRestore();
    }
  });

  // Regression: previously returned `[]`, which under --replace silently
  // wiped models.yml. Must throw so the script exits non-zero instead.
  it("throws when every requested provider is unknown", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    try {
      expect(() => parseCliArgs(["-p", "bogus,typo"])).toThrow(
        /No known providers/,
      );
    } finally {
      warn.mockRestore();
    }
  });

  it("throws on an empty --provider value", () => {
    expect(() => parseCliArgs(["--provider="])).toThrow(/no value parsed/);
  });
});
