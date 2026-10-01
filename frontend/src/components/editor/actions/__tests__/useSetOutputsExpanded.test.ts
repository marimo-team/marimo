/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import type { OutputMessage } from "@/core/kernel/messages";
import { outputExpansionConfigs } from "../useSetOutputsExpanded";

const output: OutputMessage = {
  channel: "output",
  mimetype: "text/plain",
  data: "hello",
  timestamp: 0,
};

describe("outputExpansionConfigs", () => {
  const [withOutput, withoutOutput, expanded] = MockNotebook.cellIds();
  const notebook = MockNotebook.notebookState({
    cellData: {
      [withOutput]: {},
      [withoutOutput]: {},
      [expanded]: { config: { expand_output: true } },
    },
    cellRuntime: {
      [withOutput]: { output },
      [expanded]: { output },
    },
  });

  it("expands clamped cells that have output", () => {
    expect(outputExpansionConfigs(notebook, true)).toEqual({
      [withOutput]: { expand_output: true },
    });
  });

  it("clamps every expanded cell", () => {
    expect(outputExpansionConfigs(notebook, false)).toEqual({
      [expanded]: { expand_output: false },
    });
  });
});
