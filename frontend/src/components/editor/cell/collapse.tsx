/* Copyright 2024 Marimo. All rights reserved. */
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  ChevronsUpDownIcon,
} from "lucide-react";
import type React from "react";

interface Props {
  isCollapsed: boolean;
  canCollapse: boolean;
  onClick: () => void;
}

export const CollapseToggle: React.FC<Props> = (props) => {
  // It could be collapsed, but the markdown headers were removed.
  // So we still want to be able to uncollapse it, if it is collapsed.
  if (!props.canCollapse && !props.isCollapsed) {
    return null;
  }

  return (
    <Button variant="text" size="icon" onClick={props.onClick}>
      <Arrow isCollapsed={props.isCollapsed} />
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
  count: number;
}> = ({ onClick, count }) => {
  return (
    <div
      onClick={onClick}
      className={cn(
        "flex items-center justify-center w-[calc(100%-2rem)] h-9 bg-muted gap-2 rounded-b mx-4 mb-2 opacity-80 hover:opacity-100",
      )}
    >
      <ChevronsUpDownIcon className="w-4 h-4 flex-shrink-0" />
      <span className="text-sm text-gray-500">
        {count} {count === 1 ? "cell" : "cells"} collapsed
      </span>
    </div>
  );
};
