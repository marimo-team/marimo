/* Copyright 2026 Marimo. All rights reserved. */

import { expect, test } from "vitest";
import { matchingPageRanges } from "../pagination";

test("empty prefix returns no ranges", () => {
  expect(matchingPageRanges("", 500)).toEqual([]);
});

test("zero prefix returns no ranges", () => {
  expect(matchingPageRanges("0", 500)).toEqual([]);
});

test("leading-zero prefix returns no ranges", () => {
  expect(matchingPageRanges("01", 500)).toEqual([]);
});

test("single digit prefix", () => {
  expect(matchingPageRanges("5", 500)).toEqual([
    [5, 5],
    [50, 59],
    [500, 500],
  ]);
});

test("single digit prefix with exact totalPages boundary", () => {
  expect(matchingPageRanges("5", 55)).toEqual([
    [5, 5],
    [50, 55],
  ]);
});

test("multi-digit prefix", () => {
  expect(matchingPageRanges("12", 5000)).toEqual([
    [12, 12],
    [120, 129],
    [1200, 1299],
  ]);
});

test("prefix larger than totalPages returns no ranges", () => {
  expect(matchingPageRanges("999", 100)).toEqual([]);
});

test("prefix equal to totalPages", () => {
  expect(matchingPageRanges("100", 100)).toEqual([[100, 100]]);
});

test("prefix 1 with small totalPages", () => {
  expect(matchingPageRanges("1", 10)).toEqual([
    [1, 1],
    [10, 10],
  ]);
});

test("prefix 1 with totalPages=1", () => {
  expect(matchingPageRanges("1", 1)).toEqual([[1, 1]]);
});
