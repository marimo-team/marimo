/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import {
  type Edit,
  stagedAICellsAtom,
  useStagedAICell,
  useStagedCells,
} from "@/core/ai/staged-cells";
import { chatGenerationInProgressAtom } from "@/core/ai/state";
import { getCellEditorView } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { prepareCellCodeUpdate } from "@/core/codemirror/language/cell-code";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
import { AI_EDIT_ACTION_LABELS } from "../ai/completion-handlers";
import type { ActionButton } from "../actions/types";

const actionLabels: Record<Edit["type"], { accept: string; decline: string }> =
  {
    add_cell: { accept: "Keep cell", decline: "Discard cell" },
    update_cell: AI_EDIT_ACTION_LABELS,
    delete_cell: { accept: "Delete cell", decline: "Keep cell" },
  };

export const StagedAICellBackground: React.FC<{
  cellId: CellId;
  className?: string;
}> = ({ cellId, className }) => {
  const stagedCell = useStagedAICell(cellId);

  if (!stagedCell) {
    return null;
  }

  const cellClass =
    stagedCell.type === "delete_cell"
      ? "mo-ai-deleted-cell"
      : "mo-ai-generated-cell";

  return <div className={cn(cellClass, className)} />;
};

export function useStagedAICellActions(
  cellId: CellId | undefined,
): ActionButton[] {
  const store = useStore();
  const stagedCells = useAtomValue(stagedAICellsAtom);
  const isGenerating = useAtomValue(chatGenerationInProgressAtom);
  const { deleteStagedCell, removeStagedCell } = useStagedCells(store);
  const edit = cellId === undefined ? undefined : stagedCells.get(cellId);

  if (!edit || cellId === undefined) {
    return [];
  }

  const labels = actionLabels[edit.type];
  return [
    {
      label: labels.accept,
      disabled: isGenerating,
      handle: () => {
        if (!store.get(chatGenerationInProgressAtom)) {
          acceptStagedCell(cellId, edit, removeStagedCell, deleteStagedCell);
        }
      },
    },
    {
      label: labels.decline,
      disabled: isGenerating,
      handle: () => {
        if (!store.get(chatGenerationInProgressAtom)) {
          rejectStagedCell(cellId, edit, removeStagedCell, deleteStagedCell);
        }
      },
    },
  ];
}

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

      const update = prepareCellCodeUpdate(
        editorView.state,
        edit.previousCode,
        { initialize: true },
      );

      if (update) {
        editorView.dispatch(update);
      }
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
