/* Copyright 2024 Marimo. All rights reserved. */
import { expect, it } from "vitest";
import { multiselectFilterFn } from "../multiselectFilterFn";

function filterOptions(filter: string, items: string[]) {
  return items.filter((option) => multiselectFilterFn(option, filter));
}

it("can filter to relevant words", () => {
  const options = ["a", "b", "c", "foo", "bar", "foo bar", "foobar"];

  expect(filterOptions("a", options)).toEqual([
    "a",
    "bar",
    "foo bar",
    "foobar",
  ]);

  expect(filterOptions("b", options)).toEqual([
    "b",
    "bar",
    "foo bar",
    "foobar",
  ]);

  expect(filterOptions("f", options)).toEqual(["foo", "foo bar", "foobar"]);

  expect(filterOptions("foo", options)).toEqual(["foo", "foo bar", "foobar"]);

  expect(filterOptions("foo ", options)).toEqual(["foo", "foo bar", "foobar"]);

  expect(filterOptions("foo b", options)).toEqual(["foo bar", "foobar"]);

  expect(filterOptions("foo ba", options)).toEqual(["foo bar", "foobar"]);

  expect(filterOptions("foo bar", options)).toEqual(["foo bar", "foobar"]);

  expect(filterOptions("foob", options)).toEqual(["foobar"]);

  expect(filterOptions("foob foo", options)).toEqual(["foobar"]);
});
