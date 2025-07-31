/* Copyright 2024 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import { getCellEditorView, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { getEditorCodeAsPython } from "@/core/codemirror/language/utils";

export function useSplitCellCallback() {
  const { splitCell, undoSplitCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }) => {
    // Save snapshot of code for undo
    const cellEditorView = getCellEditorView(opts.cellId);
    if (!cellEditorView) {
      return;
    }
    const code = getEditorCodeAsPython(cellEditorView);

    // Optimistic update
    splitCell(opts);

    const { dismiss } = toast({
      title: "Cell split",
      action: (
        <UndoButton
          data-testid="undo-split-button"
          size="sm"
          variant="outline"
          onClick={() => {
            undoSplitCell({ ...opts, snapshot: code });
            dismiss();
          }}
        >
          Undo
        </UndoButton>
      ),
    });
  });
}
