/* Copyright 2026 Marimo. All rights reserved. */

import type * as Protocol from "@marimo-team/client/protocol";
import type { createStore } from "jotai";
import { createRef } from "react";
import { vi } from "vitest";
import type { CellActions } from "@/core/cells/actions";
import { type NotebookState, notebookAtom } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import {
  type CellData,
  type CellRuntimeState,
  createCellRuntimeState,
} from "@/core/cells/types";
import type { MarimoError } from "@/core/kernel/messages";
import { Objects } from "@/utils/objects";
import { MockExecutions } from "./executions";

export const MockNotebook = {
  *cellIds() {
    // Some large number to prevent freezing when this function is misused.
    for (let i = 0; i < 10_000; i++) {
      yield CellId.create();
    }
  },

  notebookState: (opts?: {
    cellData: Record<CellId, Partial<CellData>>;
    cellRuntime?: Record<CellId, Partial<CellRuntimeState>>;
  }): NotebookState => {
    const cellData = opts?.cellData ?? {};
    const cellRuntime = opts?.cellRuntime ?? {};
    return {
      cellData: Objects.mapValues(cellData, (data, cid) => ({
        id: cid,
        code: "",
        name: `cell-${cid}`,
        config: {
          hide_code: false,
          disabled: false,
          column: null,
          expand_output: false,
          ...data.config,
        },
        serializedEditorState: null,
        ...data,
      })),
      cellIds: Object.keys(cellData) as CellId[],
      cellRuntime: Objects.mapValues(cellData, (_data, cid) =>
        createCellRuntimeState({ ...cellRuntime[cid] }),
      ),
      cellHandles: Objects.mapValues(cellData, (_data) => createRef()),
      cellLogs: [],
      history: [],
      scrollKey: null,
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
   * Set `store` to a notebook whose cells each ended in a host error.
   *
   * The host reports one error per execution, so each cell gets one.
   */
  withErrors: (
    store: ReturnType<typeof createStore>,
    errors: {
      cellId: CellId;
      cellName: string;
      code?: string;
      error: Partial<Protocol.Error>;
    }[],
  ): NotebookState => {
    const cellData: Record<string, Partial<CellData>> = {};
    for (const { cellId, cellName, code } of errors) {
      cellData[cellId] = {
        name: cellName,
        ...(code === undefined ? {} : { code }),
      };
    }
    const notebookState = MockNotebook.notebookState({ cellData });
    store.set(notebookAtom, notebookState);
    MockExecutions.seed(
      store,
      errors.map(({ cellId, error }) => MockExecutions.failed(cellId, error)),
    );
    return notebookState;
  },
};
