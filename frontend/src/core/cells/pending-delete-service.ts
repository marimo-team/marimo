/* Copyright 2024 Marimo. All rights reserved. */

import { atom, useAtom, useAtomValue } from "jotai";
import { useCallback, useEffect } from "react";
import {
  useDeleteCellCallback,
  useDeleteManyCellsCallback,
} from "@/components/editor/cell/useDeleteCell";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";

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

const pendingDeleteStateAtom = atom<Map<CellId, PendingDeleteEntry>>(new Map());

export function usePendingDeleteService() {
  const [, setState] = useAtom(pendingDeleteStateAtom);
  const notebook = useAtomValue(notebookAtom);
  const variables = useAtomValue(variablesAtom);

  const submit = useCallback(
    (cellIds: CellId[]) => {
      const entries = new Map<CellId, PendingDeleteEntry>();

      for (const cellId of cellIds) {
        const runtimeInfo = notebook.cellRuntime[cellId];

        // Build defs map for this cell
        const defs = new Map<VariableName, readonly CellId[]>();
        for (const variable of Object.values(variables)) {
          if (
            variable.declaredBy.includes(cellId) &&
            variable.usedBy.length > 0
          ) {
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

      setState(entries);
    },
    [notebook, variables, setState],
  );

  const clear = useCallback(() => {
    setState(new Map());
  }, [setState]);

  return { submit, clear };
}

export function usePendingDelete(cellId: CellId) {
  const [state, setState] = useAtom(pendingDeleteStateAtom);
  const deleteCell = useDeleteCellCallback();
  const deleteManyCells = useDeleteManyCellsCallback();

  const entry = state.get(cellId);

  // Auto-delete if all are "simple" cells
  useEffect(() => {
    if (state.size === 0) {
      return;
    }
    const entries = [...state.values()];
    if (entries.every((entry) => entry.type === "simple")) {
      if (state.size === 1) {
        deleteCell({ cellId: entries[0].cellId });
      } else {
        deleteManyCells({ cellIds: entries.map((e) => e.cellId) });
      }
      setState(new Map());
    }
  }, [state, deleteCell, deleteManyCells, setState]);

  if (!entry) {
    return { isPending: false as const };
  }

  const isPrimaryHandler = state.size === 1;

  if (!isPrimaryHandler) {
    return {
      isPending: true as const,
      isPrimaryHandler: false as const,
      ...entry,
    };
  }

  return {
    isPending: true as const,
    ...entry,
    isPrimaryHandler: true as const,
    confirm: () => {
      deleteManyCells({
        cellIds: [...state.values()].map((e) => e.cellId),
      });
      setState(new Map());
    },
    cancel: () => setState(new Map()),
  };
}
