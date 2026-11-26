/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { selectAtom } from "jotai/utils";
import {
  useDeleteCellCallback,
  useDeleteManyCellsCallback,
} from "@/components/editor/cell/useDeleteCell";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { cellExecutionInputsAtom, cellExecutionView } from "@/core/executions";
import { createKeyedSelectorHook } from "@/core/state/create-keyed-selector-hook";
import type { JotaiStore } from "@/core/state/jotai";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import { createReducerAndAtoms } from "@/utils/createReducer";

type PendingDeleteEntry =
  | {
      cellId: CellId;
      type: "simple";
    }
  | {
      cellId: CellId;
      type: "expensive";
      executionDurationMs?: number;
      defs: Map<VariableName, readonly CellId[]>;
    };

interface PendingDeleteState {
  entries: Map<CellId, PendingDeleteEntry>;
}

const initialState = (): PendingDeleteState => ({
  entries: new Map(),
});

const {
  valueAtom: pendingDeleteStateAtom,
  useActions,
  reducer,
} = createReducerAndAtoms(initialState, {
  submit: (
    state,
    action: {
      cellIds: CellId[];
      deleteCell: (args: { cellId: CellId }) => void;
      deleteManyCells: (args: { cellIds: CellId[] }) => void;
      store: JotaiStore;
    },
  ) => {
    const { cellIds, deleteCell, deleteManyCells, store } = action;
    const notebook = store.get(notebookAtom);
    const executions = store.get(cellExecutionInputsAtom);
    const variables = store.get(variablesAtom);

    const emptyCells = new Set(
      notebook.cellIds.filter((id) => notebook.cellData[id].code.trim() === ""),
    );

    const entries = new Map<CellId, PendingDeleteEntry>();
    for (const cellId of cellIds) {
      if (emptyCells.has(cellId)) {
        // Empty cells indicate user intent to delete already
        entries.set(cellId, { cellId, type: "simple" });
        continue;
      }

      // Build defs map for this cell
      const defs = new Map<VariableName, readonly CellId[]>();
      for (const variable of Object.values(variables)) {
        const declaredByThisCell = variable.declaredBy.includes(cellId);
        const usedByNonEmptyCell = variable.usedBy.some(
          (cellId) => !emptyCells.has(cellId),
        );
        if (declaredByThisCell && usedByNonEmptyCell) {
          defs.set(variable.name, variable.usedBy);
        }
      }

      let executionDurationMs: number | undefined;
      const { duration } = cellExecutionView(executions, cellId);
      if (duration !== null && duration > 2000) {
        executionDurationMs = duration;
      }

      if (defs.size === 0 && executionDurationMs === undefined) {
        entries.set(cellId, { cellId, type: "simple" });
      } else {
        entries.set(cellId, {
          cellId,
          type: "expensive",
          executionDurationMs,
          defs,
        });
      }
    }

    // Auto-delete if all are "simple" cells
    const allSimple = [...entries.values()].every(
      (entry) => entry.type === "simple",
    );
    if (entries.size > 0 && allSimple) {
      // Perform the deletion immediately
      if (entries.size === 1) {
        deleteCell({ cellId: [...entries.values()][0].cellId });
      } else {
        deleteManyCells({
          cellIds: [...entries.values()].map((e) => e.cellId),
        });
      }
      // Return empty state since we auto-deleted
      return initialState();
    }

    return {
      ...state,
      entries,
    };
  },

  clear: (state) => (state.entries.size === 0 ? state : initialState()),
});

const pendingDeleteCountAtom = selectAtom(
  pendingDeleteStateAtom,
  (state) => state.entries.size,
);

export function usePendingDeleteService() {
  const store = useStore();
  const { submit, clear } = useActions();
  const count = useAtomValue(pendingDeleteCountAtom);
  const deleteCell = useDeleteCellCallback();
  const deleteManyCells = useDeleteManyCellsCallback();
  return {
    submit: (cellIds: CellId[]) => {
      submit({ cellIds, deleteCell, deleteManyCells, store });
    },
    clear,
    idle: count === 0,
    shouldConfirmDelete: count > 1,
  };
}

const usePendingDeleteEntry = createKeyedSelectorHook(
  pendingDeleteStateAtom,
  (state, cellId: CellId) => state.entries.get(cellId),
);

export function usePendingDelete(cellId: CellId) {
  const entry = usePendingDeleteEntry(cellId);
  const count = useAtomValue(pendingDeleteCountAtom);
  const actions = useActions();
  const deleteManyCells = useDeleteManyCellsCallback();

  if (!entry) {
    return { isPending: false as const };
  }

  const canConfirmDelete = count === 1;

  if (!canConfirmDelete) {
    return {
      isPending: true as const,
      shouldConfirmDelete: false as const,
      ...entry,
    };
  }

  return {
    isPending: true as const,
    ...entry,
    shouldConfirmDelete: true as const,
    confirm: () => {
      deleteManyCells({
        cellIds: [entry.cellId],
      });
      actions.clear();
    },
    cancel: () => actions.clear(),
  };
}

export const visibleForTesting = { reducer, initialState };
