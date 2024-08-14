/* Copyright 2024 Marimo. All rights reserved. */
import { expect, test } from "vitest";
import { uniformSample } from "../uniformSample";
import {UrlDetector} from "../UrlDetector";

test("uniformSample", () => {
  const items = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];

  expect(uniformSample(items, 2)).toMatchInlineSnapshot(`
    [
      "A",
      "J",
    ]
  `);
  expect(uniformSample(items, 4)).toMatchInlineSnapshot(`
    [
      "A",
      "C",
      "F",
      "J",
    ]
  `);
  expect(uniformSample(items, 100)).toBe(items);
});

test("UrlDetector renders URLs as hyperlinks", () => {
  const text = "Check this link: https://example.com";
  const { container } = render(<UrlDetector text={text} />);
  const link = container.querySelector("a");
  expect(link).toBeInTheDocument();
  expect(link).toHaveAttribute("href", "https://example.com");
});
