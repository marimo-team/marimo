/* Copyright 2024 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { memo, useMemo } from "react";
import { cn } from "@/utils/cn";
import { createCellStateAtom } from "./cell-selection-atoms";

interface CellSelectionIndicatorProps {
  cellId: string;
  className?: string;
}

export const CellRangeSelectionIndicator = memo<CellSelectionIndicatorProps>(
  ({ cellId, className }) => {
    // Create a derived atom that only updates when this specific cell's state changes
    const cellStateAtom = useMemo(() => createCellStateAtom(cellId), [cellId]);
    const { isSelected, isCopied } = useAtomValue(cellStateAtom);

    if (!isSelected && !isCopied) {
      return null;
    }

    return (
      <div
        className={cn(
          "absolute inset-0 pointer-events-none",
          isSelected && "bg-[var(--green-3)]",
          isCopied && "bg-[var(--green-4)] transition-colors duration-150",
          className,
        )}
      />
    );
  },
);

CellRangeSelectionIndicator.displayName = "CellRangeSelectionIndicator";
