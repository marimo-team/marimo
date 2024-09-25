/* Copyright 2024 Marimo. All rights reserved. */
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import { hasOnlyOneCellAtom, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { sendDeleteCell } from "@/core/network/requests";
import useEvent from "react-use-event-hook";

export function useDeleteCellCallback() {
  const { deleteCell, undoDeleteCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }) => {
    // Can't delete the last cell
    if (hasOnlyOneCellAtom) {
      return;
    }

    const { cellId } = opts;
    // Optimistic update
    deleteCell({ cellId });
    sendDeleteCell({ cellId: cellId }).catch(() => {
      // Fall back on failure
      undoDeleteCell();
    });
    const { dismiss } = toast({
      title: "Cell deleted",
      description:
        "You can bring it back by clicking undo or through the command palette.",
      action: (
        <UndoButton
          data-testid="undo-delete-button"
          onClick={() => {
            undoDeleteCell();
            dismiss();
          }}
        />
      ),
    });
  });
}
