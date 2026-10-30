/* Copyright 2026 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import { useCellActions } from "@/core/cells/actions";
import { notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";

export function useDeleteCellCallback() {
  const { deleteCells, undoDeleteCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }) => {
    const { cellId } = opts;
    const notebook = store.get(notebookAtom);
    const isEmptyCell = (notebook.cellData[cellId]?.code ?? "").trim() === "";

    if (!deleteCells({ cellIds: [cellId] })) {
      return;
    }

    if (!isEmptyCell) {
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
    }
  });
}

export function useDeleteManyCellsCallback() {
  const { deleteCells, undoDeleteCell } = useCellActions();

  return useEvent((opts: { cellIds: CellId[] }) => {
    if (!deleteCells({ cellIds: opts.cellIds })) {
      return;
    }

    const { dismiss } = toast({
      title: "Cells deleted",
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
