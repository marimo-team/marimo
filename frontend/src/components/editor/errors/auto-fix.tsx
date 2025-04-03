/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useCellActions, notebookAtom } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { getAutoFixes } from "@/core/errors/errors";
import type { MarimoError } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { LightbulbIcon } from "lucide-react";

export const AutoFixButton = ({
  errors,
  cellId,
}: { errors: MarimoError[]; cellId: CellId; className?: string }) => {
  const { createNewCell } = useCellActions();
  const autoFixes = errors.flatMap((error) => getAutoFixes(error));

  if (autoFixes.length === 0) {
    return null;
  }

  // TODO: Add a dropdown menu with the auto-fixes, when we need to support
  // multiple fixes.
  const firstFix = autoFixes[0];

  return (
    <Tooltip content={firstFix.description} align="start">
      <Button
        size="xs"
        variant="outline"
        className="my-2 font-normal"
        onClick={() => {
          const editorView =
            store.get(notebookAtom).cellHandles[cellId].current?.editorView;
          firstFix.onFix({
            addCodeBelow: (code: string) => {
              createNewCell({
                cellId: cellId,
                autoFocus: false,
                before: false,
                code: code,
              });
            },
            editor: editorView,
            cellId: cellId,
          });
          // Focus the editor
          editorView?.focus();
        }}
      >
        <LightbulbIcon className="h-3 w-3 mr-2" />
        {firstFix.title}
      </Button>
    </Tooltip>
  );
};
