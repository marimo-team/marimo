/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue, useStore } from "jotai";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { stagedAICellsAtom, useStagedCells } from "@/core/ai/staged-cells";
import { chatGenerationInProgressAtom } from "@/core/ai/state";
import type { CellId } from "@/core/cells/ids";
import { getNextIndex } from "@/utils/arrays";
import {
  acceptStagedCell,
  rejectStagedCell,
  useStagedAICellActions,
} from "../../cell/StagedAICell";
import { scrollAndHighlightCell } from "../../links/cell-link";

export const PendingAICells: React.FC = () => {
  const [selectedCellId, setSelectedCellId] = useState<CellId | null>(null);

  const stagedAiCells = useAtomValue(stagedAICellsAtom);
  const isGenerating = useAtomValue(chatGenerationInProgressAtom);
  const listStagedCells = [...stagedAiCells.keys()];
  const selectedIndex =
    selectedCellId === null ? -1 : listStagedCells.indexOf(selectedCellId);
  const currentIndex = Math.max(0, selectedIndex);
  const selectedActions = useStagedAICellActions(listStagedCells[currentIndex]);
  const store = useStore();
  const { deleteStagedCell, removeStagedCell } = useStagedCells(store);

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
    setSelectedCellId(listStagedCells[newIndex]);
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

  const selectedEdit = stagedAiCells.get(listStagedCells[currentIndex]);
  const hasMultipleCells = listStagedCells.length > 1;

  return (
    <section
      aria-label="Review AI changes"
      className="@container/review shrink-0 border-t border-border bg-background px-3 py-2 text-sm"
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {hasMultipleCells && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="whitespace-nowrap text-muted-foreground">
              {listStagedCells.length} cells changed
            </span>
            <Button
              variant="outline"
              size="sm"
              className="chat-control chat-selector h-7 px-2 rounded-sm font-normal"
              onClick={acceptAllCompletions}
              disabled={isGenerating}
            >
              Keep all
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="chat-control chat-selector h-7 px-2 rounded-sm font-normal"
              onClick={rejectAllCompletions}
              disabled={isGenerating}
            >
              Discard all
            </Button>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2">
          {hasMultipleCells && (
            <span
              aria-hidden="true"
              className="hidden h-4 w-px bg-border @min-[600px]/review:block"
            />
          )}
          <div className="flex h-7 w-fit items-center">
            {hasMultipleCells && (
              <Button
                aria-label="Previous pending AI cell"
                variant="ghost"
                size="icon"
                className="chat-control size-6 rounded-sm"
                onClick={() => clickNext("down")}
              >
                <ChevronLeft className="size-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="chat-control h-6 px-1 rounded-sm font-normal tabular-nums whitespace-nowrap"
              onClick={() => scrollToCell(listStagedCells[currentIndex])}
            >
              <span aria-live="polite">
                {hasMultipleCells
                  ? `Cell ${currentIndex + 1} of ${listStagedCells.length}`
                  : "1 cell changed"}
              </span>
            </Button>
            {hasMultipleCells && (
              <Button
                aria-label="Next pending AI cell"
                variant="ghost"
                size="icon"
                className="chat-control size-6 rounded-sm"
                onClick={() => clickNext("up")}
              >
                <ChevronRight className="size-4" />
              </Button>
            )}
          </div>
          {selectedActions.map((action, index) => (
            <Button
              key={action.label}
              aria-label={action.label}
              variant="outline"
              size="sm"
              className="chat-control chat-selector h-7 px-2 rounded-sm font-normal"
              disabled={action.disabled}
              onClick={() => {
                action.handle();
                if (hasMultipleCells) {
                  clickNext("up");
                } else {
                  setSelectedCellId(null);
                }
              }}
            >
              {selectedEdit?.type === "delete_cell"
                ? action.label
                : index === 0
                  ? "Keep"
                  : "Discard"}
            </Button>
          ))}
        </div>
      </div>
    </section>
  );
};
