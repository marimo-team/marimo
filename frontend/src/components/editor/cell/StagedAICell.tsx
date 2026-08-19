/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { SparklesIcon } from "lucide-react";
import {
  type Edit,
  stagedAICellsAtom,
  useStagedCells,
} from "@/core/ai/staged-cells";
import { getCellEditorView } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "@/core/codemirror/language/utils";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { CompletionActionsCellFooter } from "../ai/completion-handlers";
import { useRunCell } from "./useRunCells";

export const StagedAICellBackground: React.FC<{
  cellId: CellId;
  className?: string;
}> = ({ cellId, className }) => {
  const stagedAICells = useAtomValue(stagedAICellsAtom);
  const stagedCell = stagedAICells.get(cellId);

  if (!stagedCell) {
    return null;
  }

  const cellClass =
    stagedCell.type === "delete_cell"
      ? "mo-ai-deleted-cell"
      : "mo-ai-generated-cell";

  return <div className={cn(cellClass, className)} />;
};

export const StagedAICellFooter: React.FC<{ cellId: CellId }> = ({
  cellId,
}) => {
  const store = useStore();
  const stagedAICells = useAtomValue(stagedAICellsAtom);
  const stagedAiCell = stagedAICells.get(cellId);
  const runCell = useRunCell(cellId);

  const { deleteStagedCell, removeStagedCell } = useStagedCells(store);

  if (!stagedAiCell) {
    return null;
  }

  const isDeletion = stagedAiCell.type === "delete_cell";

  const handleCompletion = (type: "accept" | "reject") => {
    const completionFunc =
      type === "accept" ? acceptStagedCell : rejectStagedCell;
    completionFunc(cellId, stagedAiCell, removeStagedCell, deleteStagedCell);
  };

  return (
    <div className="mo-ai-cell-footer">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <SparklesIcon className="size-3.5 text-(--blue-11)" />
        <span>
          {isDeletion ? "AI suggests deleting this cell" : "AI suggestion"}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <CompletionActionsCellFooter
          isLoading={false}
          onAccept={() => handleCompletion("accept")}
          onDecline={() => handleCompletion("reject")}
          size="xs"
          runCell={isDeletion ? undefined : runCell}
          acceptLabel={isDeletion ? "Delete" : undefined}
          declineLabel={isDeletion ? "Keep" : undefined}
        />
      </div>
    </div>
  );
};

/**
 * Accept a staged cell and apply the changes.
 */
export function acceptStagedCell(
  cellId: CellId,
  edit: Edit,
  removeStagedCell: (cellId: CellId) => void,
  deleteStagedCell: (cellId: CellId) => void,
): void {
  switch (edit.type) {
    case "delete_cell":
      // For delete cells, the cell is deleted when the completion is accepted
      deleteStagedCell(cellId);
      break;
    default:
      removeStagedCell(cellId);
      break;
  }
}

/**
 * Reject a staged cell and revert the changes.
 */
export function rejectStagedCell(
  cellId: CellId,
  edit: Edit,
  removeStagedCell: (cellId: CellId) => void,
  deleteStagedCell: (cellId: CellId) => void,
): void {
  switch (edit.type) {
    case "update_cell": {
      // Revert cell code
      const editorView = getCellEditorView(cellId);
      if (!editorView) {
        Logger.error("Editor for this cell not found", { cellId });
        break;
      }

      updateEditorCodeFromPython(editorView, edit.previousCode);
      removeStagedCell(cellId);
      break;
    }
    case "add_cell":
      // Delete the cell since it's newly created
      deleteStagedCell(cellId);
      break;
    case "delete_cell":
      // Just remove the deletion marker - cell stays in notebook
      removeStagedCell(cellId);
      break;
  }
}
