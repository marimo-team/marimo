/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { useMemo } from "react";
import {
  useDeleteCellCallback,
  useDeleteManyCellsCallback,
} from "@/components/editor/cell/useDeleteCell";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
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

const { valueAtom: pendingDeleteStateAtom, useActions } = createReducerAndAtoms(
  initialState,
  {
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
      const variables = store.get(variablesAtom);

      const emptyCells = new Set(
        notebook.cellIds.inOrderIds.filter(
          (id) => notebook.cellData[id].code.trim() === "",
        ),
      );

      const entries = new Map<CellId, PendingDeleteEntry>();
      for (const cellId of cellIds) {
        if (emptyCells.has(cellId)) {
          // Empty cells indicate user intent to delete already
          entries.set(cellId, { cellId, type: "simple" });
          continue;
        }

        const runtimeInfo = notebook.cellRuntime[cellId];

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
        if (
          runtimeInfo?.runElapsedTimeMs &&
          runtimeInfo.runElapsedTimeMs > 2000
        ) {
          executionDurationMs = runtimeInfo.runElapsedTimeMs;
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

    clear: () => initialState(),
  },
);

export function usePendingDeleteService() {
  const store = useStore();
  const { submit, clear } = useActions();
  const { entries } = useAtomValue(pendingDeleteStateAtom);
  const deleteCell = useDeleteCellCallback();
  const deleteManyCells = useDeleteManyCellsCallback();
  return useMemo(
    () => ({
      submit: (cellIds: CellId[]) => {
        submit({ cellIds, deleteCell, deleteManyCells, store });
      },
      clear,
      get idle() {
        return entries.size === 0;
      },
      get shouldConfirmDelete() {
        return entries.size > 1;
      },
    }),
    [store, submit, clear, entries, deleteCell, deleteManyCells],
  );
}

export function usePendingDelete(cellId: CellId) {
  const state = useAtomValue(pendingDeleteStateAtom);
  const actions = useActions();
  const deleteManyCells = useDeleteManyCellsCallback();

  const entry = state.entries.get(cellId);

  if (!entry) {
    return { isPending: false as const };
  }

  const canConfirmDelete = state.entries.size === 1;

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
        cellIds: [...state.entries.values()].map((e) => e.cellId),
      });
      actions.clear();
    },
    cancel: () => actions.clear(),
  };
}
