/* Copyright 2024 Marimo. All rights reserved. */
import { vi } from "vitest";
import type { CellActions, NotebookState } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import type { CellData } from "@/core/cells/types";
import { MultiColumn } from "@/utils/id-tree";
import { Objects } from "@/utils/objects";

export const MockNotebook = {
  *cellIds() {
    yield CellId.create();
  },

  notebookState: (opts?: {
    cellData: Record<string, Partial<CellData>>;
  }): NotebookState => {
    const cellData = opts?.cellData || {};
    return {
      cellData: Objects.mapValues(cellData, (data, cellId) => ({
        id: cellId as CellId,
        code: "",
        name: `cell-${cellId}`,
        config: {
          hide_code: false,
          disabled: false,
          column: null,
          ...data.config,
        },
        edited: false,
        lastCodeRun: null,
        lastExecutionTime: null,
        serializedEditorState: null,
        ...data,
      })),
      cellIds: MultiColumn.from([Object.keys(cellData) as CellId[]]),
      cellRuntime: {},
      cellHandles: {},
      cellLogs: [],
      history: [],
      scrollKey: null,
      untouchedNewCells: new Set(),
    };
  },

  cellActions: (actions: Partial<CellActions> = {}): CellActions => {
    // Create a mock that has vi.fn() for all methods
    const mockActions: Record<string, () => void> = {};

    // Create vi.fn() for each action
    for (const [action, fn] of Object.entries(actions)) {
      mockActions[action] = vi.fn().mockImplementation(fn);
    }

    // Merge with provided actions
    return new Proxy(
      {},
      {
        get(_target, prop) {
          if (prop in mockActions) {
            return mockActions[prop as keyof typeof mockActions];
          }
          throw new Error(
            `Action ${String(prop)} not mocked. Please add it to MockNotebook.cellActions({})`,
          );
        },
      },
    ) as unknown as CellActions;
  },
};
