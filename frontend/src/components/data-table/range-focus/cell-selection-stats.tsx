/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { cn } from "@/utils/cn";
import { selectedCellsAtom } from "./atoms";

export const CellSelectionStats = ({ className }: { className?: string }) => {
  const selectedCells = useAtomValue(selectedCellsAtom);

  if (selectedCells.size < 2) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex items-center justify-end gap-3 px-2 py-1 text-xs text-muted-foreground shrink-0 ml-auto",
        className,
      )}
    >
      <span>Count: {selectedCells.size}</span>
      <span>Sum: --</span>
      <span>Avg: --</span>
    </div>
  );
};
