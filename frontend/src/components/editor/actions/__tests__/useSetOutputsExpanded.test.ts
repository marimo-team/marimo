/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import type { CellOutput } from "@/core/executions";
import { outputExpansionConfigs } from "../useSetOutputsExpanded";

const output: CellOutput = {
  channel: "output",
  mimetype: "text/plain",
  data: "hello",
  timestamp: 0,
};

describe("outputExpansionConfigs", () => {
  const [withOutput, withoutOutput, expanded, expandedWithoutOutput] =
    MockNotebook.cellIds();
  const notebook = MockNotebook.notebookState({
    cellData: {
      [withOutput]: {},
      [withoutOutput]: {},
      [expanded]: { config: { expand_output: true } },
      [expandedWithoutOutput]: { config: { expand_output: true } },
    },
  });
  const outputOf = (cellId: string) =>
    cellId === withOutput || cellId === expanded ? output : null;

  it("expands clamped cells with output and skips cells without output", () => {
    expect(outputExpansionConfigs(notebook, outputOf, true)).toEqual({
      [withOutput]: { expand_output: true },
    });
  });

  it("clamps all expanded cells, including those without current output", () => {
    expect(outputExpansionConfigs(notebook, outputOf, false)).toEqual({
      [expanded]: { expand_output: false },
      [expandedWithoutOutput]: { expand_output: false },
    });
  });
});
