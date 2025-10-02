/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useSetAtom } from "jotai";
import { WrenchIcon, ZapIcon, ZapOffIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tooltip } from "@/components/ui/tooltip";
import { aiCompletionCellAtom } from "@/core/ai/state";
import { notebookAtom, useCellActions } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { aiEnabledAtom } from "@/core/config/config";
import { getAutoFixes } from "@/core/errors/errors";
import type { MarimoError } from "@/core/kernel/messages";
import { store } from "@/core/state/jotai";
import { cn } from "@/utils/cn";
import { useInstantAIFix } from "./auto-fix-atom";

export const AutoFixButton = ({
  errors,
  cellId,
  className,
}: {
  errors: MarimoError[];
  cellId: CellId;
  className?: string;
}) => {
  const { instantAIFix, setInstantAIFix } = useInstantAIFix();
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

  const handleFix = () => {
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
        instantFix: instantAIFix,
      },
    });
    // Focus the editor
    editorView?.focus();
  };

  return (
    <div className={cn("flex gap-2 my-2 items-center", className)}>
      <Tooltip content={firstFix.description} align="start">
        <Button
          size="xs"
          variant="outline"
          className="font-normal"
          onClick={handleFix}
        >
          <WrenchIcon className="h-3 w-3 mr-2" />
          {firstFix.title}
        </Button>
      </Tooltip>

      {firstFix.fixType === "ai" && (
        <div className="flex items-center gap-2">
          <Switch
            checked={instantAIFix}
            onCheckedChange={() => setInstantAIFix(!instantAIFix)}
            size="sm"
            className="h-4 w-8"
            title="Toggle instant AI fix mode"
          />
          <Tooltip
            content={
              instantAIFix ? "Instant fix enabled" : "Instant fix disabled"
            }
          >
            {instantAIFix ? (
              <ZapIcon className="h-3 w-3 text-amber-500" />
            ) : (
              <ZapOffIcon className="h-3 w-3 text-muted-foreground" />
            )}
          </Tooltip>
        </div>
      )}
    </div>
  );
};
