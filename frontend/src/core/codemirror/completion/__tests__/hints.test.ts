/* Copyright 2024 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getPositionAtWordBounds } from "../hints";
import { Text } from "@codemirror/state";

const doc = Text.of([
  "# Update the data",
  "set_state(get_state())",
  "my_100_var = 100",
]);

describe("getPositionAtWordBounds", () => {
  it("should return correct start and end positions", () => {
    const pos = "# Update the data".length + 1;
    const result = getPositionAtWordBounds(doc, pos);
    expect(result).toMatchInlineSnapshot(`
      {
        "endToken": 27,
        "startToken": 18,
      }
    `);

    expect(
      doc.slice(result.startToken, result.endToken).toString(),
    ).toMatchInlineSnapshot('"set_state"');
  });

  it("should handle start of string", () => {
    const pos = "# Update the data".length;
    const result = getPositionAtWordBounds(doc, pos);
    expect(result).toMatchInlineSnapshot(`
      {
        "endToken": 17,
        "startToken": 13,
      }
    `);
    expect(
      doc.slice(result.startToken, result.endToken).toString(),
    ).toMatchInlineSnapshot('"data"');
  });

  it("should handle end of string", () => {
    const pos = "# Update the data".length + 4;
    const result = getPositionAtWordBounds(doc, pos);
    expect(result).toMatchInlineSnapshot(`
      {
        "endToken": 27,
        "startToken": 18,
      }
    `);
    expect(
      doc.slice(result.startToken, result.endToken).toString(),
    ).toMatchInlineSnapshot('"set_state"');
  });

  it("should handle nested words", () => {
    const pos = "# Update the data".length + 12;
    const result = getPositionAtWordBounds(doc, pos);
    expect(result).toMatchInlineSnapshot(`
      {
        "endToken": 37,
        "startToken": 28,
      }
    `);
    expect(
      doc.slice(result.startToken, result.endToken).toString(),
    ).toMatchInlineSnapshot('"get_state"');
  });

  it("should handle numbers", () => {
    const pos = doc.length - 10;
    const result = getPositionAtWordBounds(doc, pos);
    expect(result).toMatchInlineSnapshot(`
      {
        "endToken": 51,
        "startToken": 41,
      }
    `);
    expect(
      doc.slice(result.startToken, result.endToken).toString(),
    ).toMatchInlineSnapshot('"my_100_var"');
  });
});
