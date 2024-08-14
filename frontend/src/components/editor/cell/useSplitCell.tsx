/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/ui/button";
import { toast } from "@/components/ui/use-toast";
import { useCellActions } from "@/core/cells/cells";
import { CellId } from "@/core/cells/ids";
import useEvent from "react-use-event-hook";

export function useSplitCellCallback() {
  const { splitCell, undoSplitCell } = useCellActions();

  return useEvent((opts: { cellId: CellId }) => {
    // Optimistic update
    splitCell(opts);

    const { dismiss } = toast({
      title: "Cell split",
      description:
        "You can unsplit the cell by clicking undo or through the command palette.",
      action: (
        <Button
          data-testid="undo-split-button"
          size="sm"
          variant="outline"
          onClick={() => {
            undoSplitCell(opts);
            dismiss();
          }}
        >
          Undo
        </Button>
      ),
    });
  });
}
