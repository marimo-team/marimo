/* Copyright 2024 Marimo. All rights reserved. */

import { createRef } from "react";
import { vi } from "vitest";
import type { CellActions, NotebookState } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import {
  type CellData,
  type CellRuntimeState,
  createCellRuntimeState,
} from "@/core/cells/types";
import type { MarimoError } from "@/core/kernel/messages";
import { MultiColumn } from "@/utils/id-tree";
import { Objects } from "@/utils/objects";

export const MockNotebook = {
  *cellIds() {
    // Some large number to prevent freezing when this function is misused.
    for (let i = 0; i < 10_000; i++) {
      yield CellId.create();
    }
  },

  notebookState: (opts?: {
    cellData: Record<string, Partial<CellData>>;
    cellRuntime?: Record<string, Partial<CellRuntimeState>>;
  }): NotebookState => {
    const cellData = opts?.cellData || {};
    const cellRuntime = opts?.cellRuntime || {};
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
      cellRuntime: Objects.mapValues(cellData, (_data, cellId) =>
        createCellRuntimeState({ ...(cellRuntime[cellId] || {}) }),
      ),
      cellHandles: Objects.mapValues(cellData, (_data) => createRef()),
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

  /**
   * Create properly typed MarimoError objects for testing
   */
  errors: {
    setupRefs: (): MarimoError => ({
      type: "setup-refs",
      edges_with_vars: [],
    }),

    cycle: (): MarimoError => ({
      type: "cycle",
      edges_with_vars: [],
    }),

    multipleDefs: (name: string): MarimoError => ({
      type: "multiple-defs",
      name,
      cells: [],
    }),

    importStar: (msg: string): MarimoError => ({
      type: "import-star",
      msg,
    }),

    exception: (msg: string, exception_type = "RuntimeError"): MarimoError => ({
      type: "exception",
      msg,
      exception_type,
      raising_cell: null,
    }),

    strictException: (msg: string, ref: string): MarimoError => ({
      type: "strict-exception",
      msg,
      ref,
      blamed_cell: null,
    }),

    interruption: (): MarimoError => ({
      type: "interruption",
    }),

    syntax: (msg: string): MarimoError => ({
      type: "syntax",
      msg,
    }),

    unknown: (msg: string): MarimoError => ({
      type: "unknown",
      msg,
      error_type: null,
    }),
  },

  /**
   * Create a notebook state with error outputs for testing ErrorContextProvider
   */
  notebookStateWithErrors: (
    errors: {
      cellId: CellId;
      cellName: string;
      errorData: MarimoError[];
    }[],
  ): NotebookState => {
    const cellData: Record<string, Partial<CellData>> = {};

    for (const error of errors) {
      cellData[error.cellId] = {
        name: error.cellName,
      };
    }

    const notebookState = MockNotebook.notebookState({ cellData });

    // Add error outputs to cell runtime
    for (const error of errors) {
      notebookState.cellRuntime[error.cellId] = {
        ...createCellRuntimeState(),
        output: {
          channel: "marimo-error" as const,
          data: error.errorData,
          mimetype: "application/vnd.marimo+error" as const,
          timestamp: Date.now(),
        },
      };
    }

    return notebookState;
  },

  /**
   * Create a single cell with errors for quick testing
   */
  cellWithErrors: (cellName: string, errorData: MarimoError[]) => {
    const cellId = CellId.create();
    return {
      cellId,
      cellName,
      errorData,
      notebookState: MockNotebook.notebookStateWithErrors([
        {
          cellId,
          cellName,
          errorData,
        },
      ]),
    };
  },
};
