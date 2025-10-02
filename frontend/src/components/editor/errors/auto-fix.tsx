/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useSetAtom } from "jotai";
import { WrenchIcon, ZapIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { notebookAtom, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { aiEnabledAtom } from "@/core/config/config";
import { getAutoFixes } from "@/core/errors/errors";
import type { MarimoError } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { cn } from "@/utils/cn";

export const AutoFixButton = ({
  errors,
  cellId,
  className,
}: {
  errors: MarimoError[];
  cellId: CellId;
  className?: string;
}) => {
  const { createNewCell } = useCellActions();
  const aiEnabled = useAtomValue(aiEnabledAtom);
  const autoFixes = errors.flatMap((error) =>
    getAutoFixes(error, { aiEnabled }),
  );
  const setAiCompletionCell = useSetAtom(aiCompletionCellAtom);

  if (autoFixes.length === 0) {
    return null;
  }

  // TODO: Add a dropdown menu with the auto-fixes, when we need to support
  // multiple fixes.
  const firstFix = autoFixes[0];

  const handleFix = (aiInstantFix = false) => {
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
      aiFix: {
        setAiCompletionCell,
        instantFix: aiInstantFix,
      },
    });
    // Focus the editor
    editorView?.focus();
  };

  return (
    <div className={cn("flex gap-2 my-2", className)}>
      <Tooltip content={firstFix.description} align="start">
        <Button
          size="xs"
          variant="outline"
          className="font-normal"
          onClick={() => handleFix(false)}
        >
          <WrenchIcon className="h-3 w-3 mr-2" />
          {firstFix.title}
        </Button>
      </Tooltip>

      {firstFix.fixType === "ai" && (
        <Tooltip content="Instant fix" align="start">
          <Button size="xs" variant="ghost" onClick={() => handleFix(true)}>
            <ZapIcon className="h-3 w-3" />
          </Button>
        </Tooltip>
      )}
    </div>
  );
};
