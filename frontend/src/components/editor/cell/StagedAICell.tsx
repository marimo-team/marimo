/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import { CompletionActionsCellFooter } from "../ai/completion-handlers";

export const StagedAICellBackground: React.FC<{
  cellId: CellId;
  className?: string;
}> = ({ cellId, className }) => {
  const stagedAICells = useAtomValue(stagedAICellsAtom);

  if (!stagedAICells.has(cellId)) {
    return null;
  }

  return <div className={cn("mo-ai-generated-cell", className)} />;
};

export const StagedAICellFooter: React.FC<{ cellId: CellId }> = ({
  cellId,
}) => {
  const store = useStore();
  const stagedAICells = useAtomValue(stagedAICellsAtom);
  const { deleteStagedCell, removeStagedCell } = useStagedCells(store);

  if (!stagedAICells.has(cellId)) {
    return null;
  }

  const handleAcceptCompletion = () => {
    removeStagedCell(cellId);
  };

  const handleDeclineCompletion = () => {
    deleteStagedCell(cellId);
  };

  return (
    <div className="flex items-center justify-end gap-1.5 w-full pb-1 pt-2">
      <CompletionActionsCellFooter
        isLoading={false}
        onAccept={handleAcceptCompletion}
        onDecline={handleDeclineCompletion}
        size="xs"
      />
    </div>
  );
};
