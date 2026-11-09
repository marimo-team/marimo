/* Copyright 2026 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import { useCellActions } from "@/core/cells/actions";
import type { CellId } from "@/core/cells/ids";

export function useMergeCellBelowCallback() {
  const { mergeCellBelow, undoDeleteCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }): boolean => {
    if (!mergeCellBelow(opts)) {
      toast({
        title: "Nothing to merge",
        description:
          "Cells merge with a visible cell below them in the same column, in the same language.",
      });
      return false;
    }

    const { dismiss } = toast({
      title: "Cells merged",
      action: (
        <UndoButton
          data-testid="undo-merge-button"
          onClick={() => {
            undoDeleteCell();
            dismiss();
          }}
        />
      ),
    });
    return true;
  });
}
