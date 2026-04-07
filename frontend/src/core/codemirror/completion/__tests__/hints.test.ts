/* Copyright 2026 Marimo. All rights reserved. */

import { EditorState, Text } from "@codemirror/state";
import { describe, expect, it } from "vitest";
import { copilotIgnore } from "@valtown/codemirror-codeium";
import { getPositionAtWordBounds, hideTooltipOnCopilotChange } from "../hints";

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

  it("should include function name when cursor inside empty call", () => {
    const callDoc = Text.of(["func()"]);
    const pos = "func(".length;
    const result = getPositionAtWordBounds(callDoc, pos);

    expect(result).toMatchInlineSnapshot(`
      {
        "endToken": 4,
        "startToken": 0,
      }
    `);
    expect(
      callDoc.slice(result.startToken, result.endToken).toString(),
    ).toMatchInlineSnapshot('"func"');
  });
});

describe("hideTooltipOnCopilotChange", () => {
  function createState(doc = "hello world") {
    return EditorState.create({ doc });
  }

  it("should hide on regular document changes", () => {
    const state = createState();
    const tr = state.update({ changes: { from: 0, insert: "x" } });
    expect(hideTooltipOnCopilotChange(tr)).toBe(true);
  });

  it("should hide on selection changes", () => {
    const state = createState();
    const tr = state.update({ selection: { anchor: 3 } });
    expect(hideTooltipOnCopilotChange(tr)).toBe(true);
  });

  it("should NOT hide on copilotIgnore-annotated changes", () => {
    const state = createState();
    const tr = state.update({
      changes: { from: 5, insert: " ghost text" },
      annotations: copilotIgnore.of(null),
    });
    expect(hideTooltipOnCopilotChange(tr)).toBe(false);
  });

  it("should NOT hide on no-op transactions", () => {
    const state = createState();
    const tr = state.update({});
    expect(hideTooltipOnCopilotChange(tr)).toBe(false);
  });
});
