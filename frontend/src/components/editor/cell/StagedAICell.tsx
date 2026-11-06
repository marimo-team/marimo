/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import {
  type Edit,
  useStagedAICell,
  useStagedCells,
} from "@/core/ai/staged-cells";
import { chatGenerationInProgressAtom } from "@/core/ai/state";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
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
  const edit = useStagedAICell(cellId);
  const isGenerating = useAtomValue(chatGenerationInProgressAtom);
  const { acceptStagedCell, rejectStagedCell } = useStagedCells(store);

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
          acceptStagedCell(cellId, edit);
        }
      },
    },
    {
      label: labels.decline,
      disabled: isGenerating,
      handle: () => {
        if (!store.get(chatGenerationInProgressAtom)) {
          rejectStagedCell(cellId, edit);
        }
      },
    },
  ];
}
