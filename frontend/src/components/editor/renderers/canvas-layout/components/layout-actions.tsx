/* Copyright 2024 Marimo. All rights reserved. */

import { ControlButton } from "@xyflow/react";
import { GitBranchIcon, Trash2Icon } from "lucide-react";
import React, { memo } from "react";
import useEvent from "react-use-event-hook";
import type {
  LayoutDirection,
  LayoutRanker,
} from "@/components/dependency-graph/types";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface LayoutActionsProps {
  onApplyLayout: (direction: LayoutDirection, ranker: LayoutRanker) => void;
  onDeleteEmptyCells: () => void;
}

// Constants
const LAYOUT_ALGORITHMS: Array<{
  direction: LayoutDirection;
  ranker: LayoutRanker;
  label: string;
}> = [
  { direction: "TB", ranker: "longest-path", label: "Longest Path" },
  { direction: "TB", ranker: "network-simplex", label: "Network Simplex" },
  { direction: "TB", ranker: "tight-tree", label: "Tight Tree" },
] as const;

/**
 * Layout actions control for applying different layout algorithms and cell management
 */
const LayoutActionsComponent: React.FC<LayoutActionsProps> = ({
  onApplyLayout,
  onDeleteEmptyCells,
}) => {
  const handleLayoutClick = useEvent(
    (direction: LayoutDirection, ranker: LayoutRanker) => {
      onApplyLayout(direction, ranker);
    },
  );

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <ControlButton title="Layout options">
          <GitBranchIcon className="h-4 w-4" />
        </ControlButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="right" align="end">
        <DropdownMenuLabel>Layout Algorithms</DropdownMenuLabel>
        {LAYOUT_ALGORITHMS.map((algorithm) => (
          <DropdownMenuItem
            key={algorithm.label}
            onClick={() =>
              handleLayoutClick(algorithm.direction, algorithm.ranker)
            }
          >
            {algorithm.label}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Cell Actions</DropdownMenuLabel>
        <DropdownMenuItem onClick={onDeleteEmptyCells}>
          <Trash2Icon className="h-4 w-4 mr-2" />
          Delete Empty Cells
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const LayoutActions = memo(LayoutActionsComponent);
LayoutActions.displayName = "LayoutActions";
