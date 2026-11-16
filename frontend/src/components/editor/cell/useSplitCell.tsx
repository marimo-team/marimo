/* Copyright 2026 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import { getCellEditorView } from "@/core/cells/cells";
import { useCellActions } from "@/core/cells/actions";
import type { CellId } from "@/core/cells/ids";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";

export function useSplitCellCallback() {
  const { splitCell, undoSplitCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }): CellId | null => {
    // Save snapshot of code for undo
    const cellEditorView = getCellEditorView(opts.cellId);
    if (!cellEditorView) {
      return null;
    }
    const code = getEditorCodeAsPython(cellEditorView);

    const newCellId = splitCell(opts);
    if (newCellId === null) {
      return null;
    }

    const { dismiss } = toast({
      title: "Cell split",
      action: (
        <UndoButton
          data-testid="undo-split-button"
          size="sm"
          variant="outline"
          onClick={() => {
            undoSplitCell({ ...opts, newCellId, snapshot: code });
            dismiss();
          }}
        >
          Undo
        </UndoButton>
      ),
    });
    return newCellId;
  });
}
