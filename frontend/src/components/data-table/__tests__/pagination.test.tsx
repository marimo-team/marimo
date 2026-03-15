/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "vitest";
import { getPageRanges } from "../pagination";
import type { PageRange } from "../types";

function getLabels(currentPage: number): string[] {
  const ranges = getPageRanges(currentPage, 200);
  return ranges.map((item: PageRange) =>
    item.type === "ellipsis" ? "..." : String(item.page),
  );
}

test("pagination start / middle / end", () => {
  expect(getLabels(1)).toMatchInlineSnapshot(`
    [
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
      "10",
      "...",
      "96",
      "97",
      "98",
      "99",
      "100",
      "101",
      "102",
      "103",
      "104",
      "105",
      "...",
      "191",
      "192",
      "193",
      "194",
      "195",
      "196",
      "197",
      "198",
      "199",
      "200",
    ]
  `);

  // all fall in the top/middle/bottom 10
  expect(getLabels(1)).toEqual(getLabels(10));
  expect(getLabels(96)).toEqual(getLabels(105));
  expect(getLabels(191)).toEqual(getLabels(200));

  // Check off by one
  expect(getLabels(1)).not.toEqual(getLabels(11));
  expect(getLabels(1)).not.toEqual(getLabels(95));
  expect(getLabels(1)).not.toEqual(getLabels(106));
  expect(getLabels(1)).not.toEqual(getLabels(190));
});

test("pagination lower middle", () => {
  expect(getLabels(50)).toMatchInlineSnapshot(`
    [
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
      "10",
      "...",
      "50",
      "...",
      "96",
      "97",
      "98",
      "99",
      "100",
      "101",
      "102",
      "103",
      "104",
      "105",
      "...",
      "191",
      "192",
      "193",
      "194",
      "195",
      "196",
      "197",
      "198",
      "199",
      "200",
    ]
  `);
});

test("pagination upper middle", () => {
  expect(getLabels(150)).toMatchInlineSnapshot(`
    [
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
      "10",
      "...",
      "96",
      "97",
      "98",
      "99",
      "100",
      "101",
      "102",
      "103",
      "104",
      "105",
      "...",
      "150",
      "...",
      "191",
      "192",
      "193",
      "194",
      "195",
      "196",
      "197",
      "198",
      "199",
      "200",
    ]
  `);
});
