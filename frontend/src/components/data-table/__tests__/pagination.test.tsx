/* Copyright 2024 Marimo. All rights reserved. */

import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import { Functions } from "@/utils/functions";
import { PageSelector } from "../pagination";

function getOptions(currentPage: number) {
  const { container } = render(
    <PageSelector
      currentPage={currentPage}
      totalPages={200}
      onPageChange={Functions.NOOP}
    />,
  );

  const options = container.querySelectorAll("option");
  const optionValues = [...options].map((option) => option.textContent);
  return optionValues;
}

test("pagination start / middle / end", () => {
  expect(getOptions(1)).toMatchInlineSnapshot(`
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
  expect(getOptions(1)).toEqual(getOptions(10));
  expect(getOptions(96)).toEqual(getOptions(105));
  expect(getOptions(191)).toEqual(getOptions(200));

  // Check off by one
  expect(getOptions(1)).not.toEqual(getOptions(11));
  expect(getOptions(1)).not.toEqual(getOptions(95));
  expect(getOptions(1)).not.toEqual(getOptions(106));
  expect(getOptions(1)).not.toEqual(getOptions(190));
});

test("pagination lower middle", () => {
  expect(getOptions(50)).toMatchInlineSnapshot(`
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
  expect(getOptions(150)).toMatchInlineSnapshot(`
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
