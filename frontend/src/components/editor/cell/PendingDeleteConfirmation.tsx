/* Copyright 2024 Marimo. All rights reserved. */

import { AlertTriangleIcon } from "lucide-react";
import React from "react";
import { FocusScope } from "react-aria";
import { formatElapsedTime } from "@/components/editor/cell/CellStatus";
import { CellLink } from "@/components/editor/links/cell-link";
import { Button } from "@/components/ui/button";
import type { CellId } from "@/core/cells/ids";
import { usePendingDelete } from "@/core/cells/pending-delete-service";
import { cn } from "@/utils/cn";

export const PendingDeleteConfirmation: React.FC<{ cellId: CellId }> = ({
  cellId,
}) => {
  const pendingDelete = usePendingDelete(cellId);

  if (!pendingDelete.isPending) {
    return null;
  }

  // Non-primary handlers in multi-delete just show pending state
  if (pendingDelete.type === "simple") {
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

  const hasExpensiveExecution = pendingDelete.executionDurationMs !== undefined;
  const hasDependencies = pendingDelete.defs.size > 0;
  const formattedTime = formatElapsedTime(
    pendingDelete.executionDurationMs ?? 0,
  );

  let warningMessage = "Pending deletion";
  if (hasExpensiveExecution && hasDependencies) {
    warningMessage = `This cell took ${formattedTime} to run and contains variables referenced by other cells.`;
  } else if (hasExpensiveExecution) {
    warningMessage = `This cell took ${formattedTime} to run.`;
  } else if (hasDependencies) {
    warningMessage = "This cell contains variables referenced by other cells.";
  }

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
              [...pendingDelete.defs.entries()].map(([varName, cells]) => (
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
          </div>
          {/* Only show buttons for single cell - multi-cell uses toast */}
          {pendingDelete.shouldConfirmDelete && (
            <>
              <p className="text-[var(--amber-11)] mt-2 mb-3">
                Are you sure you want to delete?
              </p>
              <FocusScope autoFocus={true}>
                <div
                  className="flex items-center gap-2"
                  onKeyDown={(e) => {
                    // Stop propagation to prevent Cell's resumeCompletionHandler
                    e.stopPropagation();
                  }}
                >
                  <Button
                    size="xs"
                    variant="ghost"
                    onClick={() => pendingDelete.cancel()}
                    className="text-[var(--amber-11)] hover:bg-[var(--amber-4)] hover:text-[var(--amber-11)]"
                  >
                    Cancel
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => pendingDelete.confirm()}
                    className="bg-[var(--amber-11)] hover:bg-[var(--amber-12)] text-white border-[var(--amber-11)]"
                  >
                    Delete
                  </Button>
                </div>
              </FocusScope>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
