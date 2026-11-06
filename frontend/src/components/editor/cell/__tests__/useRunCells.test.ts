/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { MockExecutions } from "@/__mocks__/executions";
import { MockNotebook } from "@/__mocks__/notebook";
import { cellId } from "@/__tests__/branded";
import {
  cellExecutionInputsAtom,
  cellExecutionView,
  notebookQueuedOrRunningCountAtom,
} from "@/core/executions";
import { store } from "@/core/state/jotai";
import { runCells } from "../useRunCells";

const ENABLED = cellId("enabled");
const DISABLED = cellId("disabled");

describe("runCells", () => {
  it("sends a disabled cell to the kernel without reading it as queued", async () => {
    MockExecutions.seed(store, []);
    const notebook = MockNotebook.notebookState({
      cellData: {
        [ENABLED]: { code: "x = 1" },
        [DISABLED]: { code: "y = 2", config: { disabled: true } },
      },
    });
    const sendRun = vi.fn(async () => null);

    await runCells({
      cellIds: [ENABLED, DISABLED],
      sendRun,
      prepareForRun: vi.fn(),
      notebook,
    });

    expect(sendRun).toHaveBeenCalledWith({
      cellIds: [ENABLED, DISABLED],
      codes: ["x = 1", "y = 2"],
    });
    const inputs = store.get(cellExecutionInputsAtom);
    expect(cellExecutionView(inputs, ENABLED).status).toBe("queued");
    expect(cellExecutionView(inputs, DISABLED).status).toBe("idle");
    expect(store.get(notebookQueuedOrRunningCountAtom)).toBe(1);
  });
});
