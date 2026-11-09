/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { formatDuration } from "../format-duration";

describe("formatDuration", () => {
  it.each([
    [200, "1s"],
    [8_400, "8s"],
    [60_000, "1m"],
    [65_000, "1m 5s"],
    [3_600_000, "1h"],
    [3_780_000, "1h 3m"],
  ])("%d ms → %s", (ms, expected) => {
    expect(formatDuration(ms)).toBe(expected);
  });
});
