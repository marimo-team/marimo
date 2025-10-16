/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import { getCellEditorView } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { updateEditorCodeFromPython } from "@/core/codemirror/language/utils";
import { cn } from "@/utils/cn";
import { Logger } from "@/utils/Logger";
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
  const stagedAiCell = stagedAICells.get(cellId);

  const { deleteStagedCell, removeStagedCell } = useStagedCells(store);

  if (!stagedAiCell) {
    return null;
  }

  const handleAcceptCompletion = () => {
    removeStagedCell(cellId);
  };

  const handleDeclineCompletion = () => {
    switch (stagedAiCell.type) {
      case "update_cell": {
        // Revert cell code
        const editorView = getCellEditorView(cellId);
        if (!editorView) {
          Logger.error("Editor for this cell not found", { cellId });
          break;
        }

        updateEditorCodeFromPython(editorView, stagedAiCell.previousCode);
        removeStagedCell(cellId);
        break;
      }
      case "add_cell":
        // Delete the cell since it's newly created
        deleteStagedCell(cellId);
        break;
      case "delete_cell":
        // TODO: Revert delete
        removeStagedCell(cellId);
        break;
    }
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
