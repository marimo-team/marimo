/* Copyright 2026 Marimo. All rights reserved. */

import useEvent from "react-use-event-hook";
import { UndoButton } from "@/components/buttons/undo-button";
import { toast } from "@/components/ui/use-toast";
import {
  type MergeBlocker,
  type MergeResult,
  useCellActions,
} from "@/core/cells/actions";
import type { CellId } from "@/core/cells/ids";

const BLOCKED: Record<MergeBlocker, string> = {
  "no-cell-below": "There is no visible cell below in this column.",
  "different-language":
    "Only cells of the same language merge, and SQL cells hold one query each.",
  "different-disabled": "One cell is disabled and the other is not.",
  running: "The cell below is running or queued.",
  "both-named": "Both cells are named. Remove one name first.",
};

export function useMergeCellBelowCallback() {
  const { mergeCellBelow, undoDeleteCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }): MergeResult => {
    const result = mergeCellBelow(opts);
    if (!result.merged) {
      toast({
        title: "Can't merge these cells",
        description: BLOCKED[result.blocker],
      });
      return result;
    }

    const { dismiss } = toast({
      title: "Cells merged",
      action: (
        <UndoButton
          data-testid="undo-merge-button"
          onClick={() => {
            dismiss();
            if (!undoDeleteCell({ only: result.entry })) {
              toast({
                title: "Can't undo this merge here",
                description: "Undo the changes made after it first.",
              });
            }
          }}
        />
      ),
    });
    return result;
  });
}
