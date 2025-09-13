/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { SparklesIcon } from "lucide-react";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import type { CellId } from "@/core/cells/ids";
import { CompletionActionsCellFooter } from "../ai/completion-handlers";

export const StagedAICellBackground: React.FC<{ cellId: CellId }> = ({
  cellId,
}) => {
  const stagedAICells = useAtomValue(stagedAICellsAtom);

  if (!stagedAICells.cellsMap.has(cellId)) {
    return null;
  }

  return (
    <>
      {/* <div
        data-testid="completion-cell-background"
        className="absolute top-0 left-0 h-full w-full z-10 bg-blue-400/10 rounded-b-md pointer-events-none"
      /> */}
      <div className="absolute bottom-0 z-5 right-0 flex items-center gap-1 bg-(--blue-5) px-2 py-1 rounded-tl-md rounded-br-sm mr-auto ml-1 pointer-events-none">
        <SparklesIcon className="size-3.5 text-(--blue-11)" />
        <span className="text-xs text-(--blue-12)">AI</span>
      </div>
    </>
  );
};

export const StagedAICellFooter: React.FC<{ cellId: CellId }> = ({
  cellId,
}) => {
  const stagedAICells = useAtomValue(stagedAICellsAtom);
  const { deleteStagedCell, removeStagedCell } = useStagedCells();

  if (!stagedAICells.cellsMap.has(cellId)) {
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
