/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { ChevronDown, ChevronUp, SparklesIcon } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import type { CellId } from "@/core/cells/ids";
import { getNextIndex } from "@/utils/arrays";
import { cn } from "@/utils/cn";
import {
  AcceptCompletionButton,
  RejectCompletionButton,
} from "../../ai/completion-handlers";
import { acceptStagedCell, rejectStagedCell } from "../../cell/StagedAICell";
import { useRunCells } from "../../cell/useRunCells";
import { scrollAndHighlightCell } from "../../links/cell-link";

export const PendingAICells: React.FC = () => {
  const [currentIndex, setCurrentIndex] = useState<number | null>(null);

  const stagedAiCells = useAtomValue(stagedAICellsAtom);
  const listStagedCells = [...stagedAiCells.keys()];
  const store = useStore();
  const { deleteStagedCell, removeStagedCell } = useStagedCells(store);
  const runCell = useRunCells();

  if (stagedAiCells.size === 0) {
    return null;
  }

  const scrollToCell = (cellId: CellId) => {
    scrollAndHighlightCell(cellId, "focus");
  };

  const clickNext = (direction: "up" | "down") => {
    const newIndex = getNextIndex(
      currentIndex,
      listStagedCells.length,
      direction,
    );
    setCurrentIndex(newIndex);
    scrollToCell(listStagedCells[newIndex]);
  };

  const acceptAllCompletions = () => {
    for (const [cellId, edit] of stagedAiCells) {
      acceptStagedCell(cellId, edit, removeStagedCell, deleteStagedCell);
    }
  };

  const rejectAllCompletions = () => {
    for (const [cellId, edit] of stagedAiCells) {
      rejectStagedCell(cellId, edit, removeStagedCell, deleteStagedCell);
    }
  };

  const runAllCells = () => {
    runCell(listStagedCells);
  };

  const cyanShadow = "shadow-[0_0_6px_0_#00A2C733]";

  return (
    <div
      className={cn(
        "fixed bottom-16 left-1/2 transform -translate-x-1/2 z-50 bg-background/95 backdrop-blur-sm supports-backdrop-filter:bg-background/80 border border-border rounded-lg px-3 py-2 flex items-center justify-between gap-2.5 w-100",
        cyanShadow,
      )}
    >
      <SparklesIcon className="h-4 w-4 text-primary" />

      <div className="flex items-center">
        <Button variant="ghost" size="icon" onClick={() => clickNext("up")}>
          <ChevronUp className="h-3.5 w-3.5" />
        </Button>
        <span className="text-xs font-mono min-w-[3.5rem] text-center">
          {currentIndex === null
            ? `${listStagedCells.length} pending`
            : `${currentIndex + 1} / ${listStagedCells.length}`}
        </span>
        <Button variant="ghost" size="icon" onClick={() => clickNext("down")}>
          <ChevronDown className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="h-5 w-px bg-border" />

      <div className="flex items-center gap-1.5">
        <AcceptCompletionButton
          multipleCompletions={true}
          onAccept={acceptAllCompletions}
          isLoading={false}
          size="xs"
          buttonStyles="h-6.5"
          runCell={runAllCells}
        />
        <RejectCompletionButton
          multipleCompletions={true}
          onDecline={rejectAllCompletions}
          size="xs"
          className="h-6.5"
        />
      </div>
    </div>
  );
};
