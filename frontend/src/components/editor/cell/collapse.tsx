/* Copyright 2024 Marimo. All rights reserved. */
import { Toolbar } from "@/components/layout/toolbar";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { getDescendantsStatus } from "@/core/cells/utils";
import { cn } from "@/utils/cn";
import {
  AlertOctagonIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsUpDownIcon,
  Loader2Icon,
  RefreshCcw,
} from "lucide-react";
import type React from "react";
import { memo } from "react";

interface Props {
  isCollapsed: boolean;
  canCollapse: boolean;
  onClick: () => void;
}

export const CollapseToggle: React.FC<Props> = (props) => {
  // It could be collapsed, but the markdown headers were removed.
  // So we still want to be able to expand it, if it is collapsed.
  if (!props.canCollapse && !props.isCollapsed) {
    return null;
  }

  return (
    <Button variant="text" size="icon" onClick={props.onClick}>
      <Tooltip content={props.isCollapsed ? "Expand" : "Collapse"}>
        <span>
          <Arrow isCollapsed={props.isCollapsed} />
        </span>
      </Tooltip>
    </Button>
  );
};

const Arrow = ({ isCollapsed }: { isCollapsed: boolean }) => {
  return isCollapsed ? (
    <ChevronRightIcon className="w-5 h-5 flex-shrink-0" />
  ) : (
    <ChevronDownIcon className="w-5 h-5 flex-shrink-0" />
  );
};

export const CollapsedCellBanner: React.FC<{
  onClick: () => void;
  cellId: CellId;
  count: number;
}> = memo(({ onClick, count, cellId }) => {
  const notebook = useNotebook();
  const states = getDescendantsStatus(notebook, cellId);

  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center justify-between w-[calc(100%-2rem)] h-9 bg-muted rounded-b mx-4 opacity-80 hover:opacity-100 cursor-pointer",
      )}
    >
      <Toolbar
        center={
          <>
            <ChevronsUpDownIcon className="w-4 h-4 flex-shrink-0" />
            <span className="text-sm text-gray-500">
              {count} {count === 1 ? "cell" : "cells"} collapsed
            </span>
          </>
        }
        right={
          <>
            {states.errored && (
              <Tooltip content="Has errors" delayDuration={100}>
                <AlertOctagonIcon className="w-4 h-4 flex-shrink-0 text-destructive" />
              </Tooltip>
            )}
            {states.stale && (
              <Tooltip content="Has stale cells" delayDuration={100}>
                <RefreshCcw className="w-4 h-4 flex-shrink-0 text-[var(--yellow-11)]" />
              </Tooltip>
            )}
            {states.runningOrQueued && (
              <Tooltip content="Running" delayDuration={100}>
                <Loader2Icon className="w-4 h-4 flex-shrink-0 animate-spin" />
              </Tooltip>
            )}
          </>
        }
      />
    </div>
  );
});
CollapsedCellBanner.displayName = "CollapsedCellBanner";
