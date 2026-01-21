/* Copyright 2026 Marimo. All rights reserved. */

import { ChevronsDownUpIcon, ChevronsUpDownIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";

interface ExpandCollapseButtonProps {
  isExpanded: boolean;
  onToggle: () => void;
  // When to display the button
  visibilityClassName?: string;
  testId?: string;
}

/**
 * Button to expand/collapse output content.
 */
export const ExpandCollapseButton = ({
  isExpanded,
  onToggle,
  visibilityClassName,
  testId = "expand-output-button",
}: ExpandCollapseButtonProps) => {
  return (
    <Button
      data-testid={testId}
      aria-label={isExpanded ? "Collapse output" : "Expand output"}
      className={cn(
        "hover:border-border border border-transparent hover:bg-muted p-1",
        !isExpanded && visibilityClassName,
      )}
      onClick={onToggle}
      size="xs"
      variant="text"
    >
      {isExpanded ? (
        <Tooltip content="Collapse output" side="left">
          <ChevronsDownUpIcon className="h-4 w-4" />
        </Tooltip>
      ) : (
        <Tooltip content="Expand output" side="left">
          <ChevronsUpDownIcon className="h-4 w-4 opacity-60" />
        </Tooltip>
      )}
    </Button>
  );
};
