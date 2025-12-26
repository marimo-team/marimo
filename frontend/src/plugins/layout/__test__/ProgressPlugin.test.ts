/* Copyright 2026 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { prettyTime } from "../ProgressPlugin";

const Cases: [number, string][] = [
  // exact values
  [0, "0s"],
  [1, "1s"],
  [5, "5s"],
  [15, "15s"],
  [60, "1m"],
  [100, "1m, 40s"],
  [60 * 60, "1h"],
  [60 * 60 * 24, "1d"],
  [60 * 60 * 24 * 7, "1w"],
  [60 * 60 * 24 * 8, "1w, 1d"],
  [60 * 60 * 24 * 30, "4w, 2d"],
  [60 * 60 * 24 * 366, "1y, 18h"],
  [60 * 60 * 24 * 466, "1y, 3mo"],
  // decimal values
  [0.5, "0.5s"],
  [1.5, "1.5s"],
  [5.2, "5.2s"],
  [5.33, "5.33s"],
  [15.2, "15s"],
  [60 * 1.5, "1m, 30s"],
  [100.2, "1m, 40s"],
  [60 * 60 * 1.5, "1h, 30m"],
  [60 * 60 * 24 * 1.5, "1d, 12h"],
  // edge cases
  [0, "0s"],
  [0.0001, "0s"],
  [0.001, "0s"],
  [0.01, "0.01s"],
];

// generate one test per pair
for (const [input, expected] of Cases) {
  test(`prettyTime(${input}) → ${expected}`, () => {
    expect(prettyTime(input)).toBe(expected);
  });
}
