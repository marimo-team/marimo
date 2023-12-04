/* Copyright 2023 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { prettyTime } from "../ProgressPlugin";

// examples of expected output
test("prettyTime", () => {
  // exact
  expect(prettyTime(0)).toMatchInlineSnapshot('"0s"');
  expect(prettyTime(1)).toMatchInlineSnapshot('"1s"');
  expect(prettyTime(60)).toMatchInlineSnapshot('"1m"');
  expect(prettyTime(60 * 60)).toMatchInlineSnapshot('"1h"');
  expect(prettyTime(60 * 60 * 24)).toMatchInlineSnapshot('"1d"');

  // decimal
  expect(prettyTime(0.5)).toMatchInlineSnapshot('"0.5s"');
  expect(prettyTime(1.5)).toMatchInlineSnapshot('"1.5s"');
  expect(prettyTime(60 * 1.5)).toMatchInlineSnapshot('"1m, 30s"');
  expect(prettyTime(60 * 60 * 1.5)).toMatchInlineSnapshot('"1h, 30m"');
  expect(prettyTime(60 * 60 * 24 * 1.5)).toMatchInlineSnapshot('"1d, 12h"');

  // edge cases
  expect(prettyTime(0)).toMatchInlineSnapshot('"0s"');
  expect(prettyTime(0.0001)).toMatchInlineSnapshot('"0s"');
  expect(prettyTime(0.001)).toMatchInlineSnapshot('"0s"');
  expect(prettyTime(0.01)).toMatchInlineSnapshot('"0.01s"');
});
