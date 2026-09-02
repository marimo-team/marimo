/* Copyright 2026 Marimo. All rights reserved. */

import {
  AlertOctagonIcon,
  ClockIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsUpDownIcon,
  Loader2Icon,
  Link2OffIcon,
  RefreshCcw,
  CircleStopIcon,
} from "lucide-react";
import type React from "react";
import { memo } from "react";
import { Toolbar } from "@/components/layout/toolbar";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { getDescendantsStatus } from "@/core/cells/utils";
import { cn } from "@/utils/cn";

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
    <ChevronRightIcon
      className="shrink-0 opacity-60"
      strokeWidth={1.8}
      size={14}
    />
  ) : (
    <ChevronDownIcon
      className="shrink-0 opacity-60"
      strokeWidth={1.8}
      size={14}
    />
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
            <ChevronsUpDownIcon className="w-4 h-4 shrink-0" />
            <span className="text-sm text-gray-500">
              {count} {count === 1 ? "cell" : "cells"} collapsed
            </span>
          </>
        }
        right={
          <>
            {states.failed && (
              <Tooltip content="Has errors" delayDuration={100}>
                <AlertOctagonIcon className="w-4 h-4 shrink-0 text-destructive" />
              </Tooltip>
            )}
            {states.outdated && (
              <Tooltip content="Has cells to run" delayDuration={100}>
                <RefreshCcw className="w-4 h-4 shrink-0 text-(--slate-11)" />
              </Tooltip>
            )}
            {states.blocked && (
              <Tooltip content="Has blocked cells" delayDuration={100}>
                <Link2OffIcon className="w-4 h-4 shrink-0 text-muted-foreground" />
              </Tooltip>
            )}
            {states.stopped && (
              <Tooltip content="Has cells stopped upstream" delayDuration={100}>
                <CircleStopIcon className="w-4 h-4 shrink-0 text-muted-foreground" />
              </Tooltip>
            )}
            {states.queued && (
              <Tooltip content="Queued" delayDuration={100}>
                <ClockIcon className="w-4 h-4 shrink-0 text-muted-foreground" />
              </Tooltip>
            )}
            {states.running && (
              <Tooltip content="Running" delayDuration={100}>
                <Loader2Icon className="w-4 h-4 shrink-0 animate-spin text-(--blue-11)" />
              </Tooltip>
            )}
          </>
        }
      />
    </div>
  );
});
CollapsedCellBanner.displayName = "CollapsedCellBanner";
