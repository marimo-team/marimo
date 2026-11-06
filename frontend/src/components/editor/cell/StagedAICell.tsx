/* Copyright 2026 Marimo. All rights reserved. */

import { atom, useAtomValue, useStore } from "jotai";
import { useMemo } from "react";
import {
  type Edit,
  stagedAICellsAtom,
  useStagedAICell,
  useStagedCells,
} from "@/core/ai/staged-cells";
import { chatGenerationInProgressAtom } from "@/core/ai/state";
import type { CellId } from "@/core/cells/ids";
import { AI_EDIT_ACTION_LABELS } from "../ai/completion-handlers";
import type { ActionButton } from "../actions/types";

const actionLabels: Record<Edit["type"], { accept: string; decline: string }> =
  {
    add_cell: { accept: "Keep cell", decline: "Discard cell" },
    update_cell: AI_EDIT_ACTION_LABELS,
    delete_cell: { accept: "Delete cell", decline: "Keep cell" },
  };

export const StagedAIDeletionMarker: React.FC<{ cellId: CellId }> = ({
  cellId,
}) =>
  useStagedAICell(cellId)?.type === "delete_cell" ? (
    <div className="mo-ai-deleted-cell" />
  ) : null;

export function useStagedAICellActions(
  cellId: CellId | undefined,
): ActionButton[] {
  const store = useStore();
  const edit = useStagedAICell(cellId);
  // Every cell calls this; only cells with a pending edit care about the lock.
  const isLocked = useAtomValue(
    useMemo(
      () =>
        atom(
          (get) =>
            cellId !== undefined &&
            get(stagedAICellsAtom).has(cellId) &&
            get(chatGenerationInProgressAtom),
        ),
      [cellId],
    ),
  );
  const { acceptStagedCell, rejectStagedCell } = useStagedCells();

  if (!edit || cellId === undefined) {
    return [];
  }

  const labels = actionLabels[edit.type];
  return [
    {
      label: labels.accept,
      disabled: isLocked,
      handle: () => {
        if (!store.get(chatGenerationInProgressAtom)) {
          acceptStagedCell(cellId, edit);
        }
      },
    },
    {
      label: labels.decline,
      disabled: isLocked,
      handle: () => {
        if (!store.get(chatGenerationInProgressAtom)) {
          rejectStagedCell(cellId, edit);
        }
      },
    },
  ];
}
