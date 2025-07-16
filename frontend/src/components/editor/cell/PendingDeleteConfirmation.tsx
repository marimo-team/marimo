/* Copyright 2024 Marimo. All rights reserved. */

import { useAtom, useAtomValue } from "jotai";
import { AlertTriangleIcon } from "lucide-react";
import React, { useEffect } from "react";
import { formatElapsedTime } from "@/components/editor/cell/CellStatus";
import { CellLink } from "@/components/editor/links/cell-link";
import { Button } from "@/components/ui/button";
import type { CellId } from "@/core/cells/ids";
import { pendingDeleteCellsAtom } from "@/core/cells/pending-delete";
import { variablesAtom } from "@/core/variables/state";
import type { VariableName } from "@/core/variables/types";
import { cn } from "@/utils/cn";
import { useDeleteCellCallback } from "./useDeleteCell";

export const PendingDeleteInformation: React.FC<
  PendingDeleteInformationProps
> = ({ executionTimeMs, cellId }) => {
  const pendingCells = useAtomValue(pendingDeleteCellsAtom);
  if (!pendingCells.has(cellId)) {
    return null;
  }
  return (
    <PendingDeleteInformationInternal
      cellId={cellId}
      executionTimeMs={executionTimeMs}
    />
  );
};

interface PendingDeleteInformationProps {
  cellId: CellId;
  executionTimeMs: number;
}

const PendingDeleteInformationInternal: React.FC<
  PendingDeleteInformationProps
> = ({ cellId, executionTimeMs }) => {
  const variables = useAtomValue(variablesAtom);
  const [pendingCells, setPendingCells] = useAtom(pendingDeleteCellsAtom);
  const deleteCell = useDeleteCellCallback();

  const defs = new Map<VariableName, readonly CellId[]>();
  for (const variable of Object.values(variables)) {
    if (variable.declaredBy.includes(cellId) && variable.usedBy.length > 0) {
      defs.set(variable.name, variable.usedBy);
    }
  }

  const hasExpensiveExecution = executionTimeMs > 2000;
  const hasDependencies = defs.size > 0;
  const isExpensiveOrHasDeps = hasExpensiveExecution || hasDependencies;
  const isMultiPending = pendingCells.size > 1;

  const autoDelete = !isMultiPending && !isExpensiveOrHasDeps;

  // Auto-delete if not expensive and not multi-pending
  useEffect(() => {
    if (autoDelete) {
      deleteCell({ cellId });
      setPendingCells(new Set());
    }
  }, [cellId, deleteCell, setPendingCells, autoDelete]);

  if (autoDelete) {
    return null;
  }

  // State 1: Part of multi-cell deletion but not expensive/dependent
  if (isMultiPending && !isExpensiveOrHasDeps) {
    return (
      <div
        className={cn(
          "px-3 py-1.5",
          "bg-[var(--amber-2)] border-t border-[var(--amber-6)]",
          "animate-in slide-in-from-top-2 duration-200",
        )}
        data-testid={`pending-delete-${cellId}`}
      >
        <div className="flex items-center gap-2">
          <AlertTriangleIcon className="w-3 h-3 text-[var(--amber-11)] flex-shrink-0" />
          <span className="text-[var(--amber-11)] text-xs">
            Pending deletion
          </span>
        </div>
      </div>
    );
  }

  const formattedTime = formatElapsedTime(executionTimeMs);
  let warningMessage = "Pending deletion";
  if (hasExpensiveExecution && hasDependencies) {
    warningMessage = `This cell took ${formattedTime} to run and contains variables referenced by other cells.`;
  } else if (hasExpensiveExecution) {
    warningMessage = `This cell took ${formattedTime} to run.`;
  } else if (hasDependencies) {
    warningMessage = "This cell contains variables referenced by other cells.";
  }

  // State 2 & 3: Single cell or multi-cell with warning
  // (For multi-cell, the toast handles the confirmation)

  return (
    <div
      className={cn(
        "px-4 py-3",
        "bg-[var(--amber-2)] border-t border-[var(--amber-6)]",
        "animate-in slide-in-from-top-2 duration-200",
      )}
      data-testid={`pending-delete-${cellId}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangleIcon className="w-4 h-4 text-[var(--amber-11)] mt-0.5 flex-shrink-0" />
        <div className="flex-1">
          <div className="font-code text-sm text-[0.84375rem]">
            <p className="text-[var(--amber-11)] font-medium">
              {warningMessage}
            </p>

            {hasDependencies &&
              [...defs.entries()].map(([varName, cells]) => (
                <div key={varName}>
                  <p className="text-[var(--amber-11)] mt-2">
                    '<span className="font-mono">{varName}</span>' is referenced
                    by:
                  </p>
                  <ul className="list-disc">
                    {cells.map((id) => (
                      <li
                        key={id}
                        className="my-0.5 ml-8 text-[var(--amber-11)]/60"
                      >
                        <CellLink cellId={id} />
                      </li>
                    ))}
                  </ul>
                </div>
              ))}

            <p className="text-[var(--amber-11)] mt-2 mb-3">
              Are you sure you want to delete?
            </p>
          </div>
          {/* Only show buttons for single cell - multi-cell uses toast */}
          {pendingCells.size === 1 && (
            <div className="flex items-center gap-2">
              <Button
                size="xs"
                variant="ghost"
                onClick={() => setPendingCells(new Set())}
                className="text-[var(--amber-11)] hover:bg-[var(--amber-4)] hover:text-[var(--amber-11)]"
              >
                Cancel
              </Button>
              <Button
                size="xs"
                variant="secondary"
                onClick={() => {
                  deleteCell({ cellId });
                  setPendingCells(new Set());
                }}
                className="bg-[var(--amber-11)] hover:bg-[var(--amber-12)] text-white border-[var(--amber-11)]"
              >
                Delete
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
