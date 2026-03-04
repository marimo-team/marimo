/* Copyright 2026 Marimo. All rights reserved. */

import {
  ChevronRightIcon,
  MoreVerticalIcon,
  RefreshCwIcon,
} from "lucide-react";
import React, { useCallback, useState } from "react";
import { cn } from "@/utils/cn";
import { Button } from "./button";
import { Tooltip } from "./tooltip";

/**
 * Animated chevron for tree expand/collapse.
 * Rotates 90° when `isExpanded` is true.
 */
export const TreeChevron: React.FC<{
  isExpanded: boolean;
  className?: string;
}> = ({ isExpanded, className }) => (
  <ChevronRightIcon
    className={cn(
      "shrink-0 transition-transform",
      isExpanded && "rotate-90",
      className,
    )}
  />
);

/**
 * Refresh button that briefly spins its icon when clicked.
 */
export const RefreshIconButton: React.FC<{
  onClick: (e: React.MouseEvent) => void;
  tooltip?: string;
  className?: string;
  iconClassName?: string;
}> = ({ onClick, tooltip = "Refresh", className, iconClassName }) => {
  const [isSpinning, setIsSpinning] = useState(false);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      setIsSpinning(true);
      onClick(e);
      // Artificially spin for 500ms to show the user that the button is working.
      setTimeout(() => setIsSpinning(false), 500);
    },
    [onClick],
  );

  const button = (
    <Button
      variant="text"
      size="xs"
      className={className}
      onClick={handleClick}
    >
      <RefreshCwIcon
        className={cn(
          "h-4 w-4",
          iconClassName,
          isSpinning && "animate-[spin_0.5s]",
        )}
      />
    </Button>
  );

  return <Tooltip content={tooltip}>{button}</Tooltip>;
};

/**
 * Three-dot menu trigger that fades in on row hover.
 * Must be inside a `group` container.
 * Forwards ref so it works with Radix `asChild`.
 */
export const MoreActionsButton = React.forwardRef<
  HTMLButtonElement,
  {
    onClick?: (e: React.MouseEvent) => void;
    className?: string;
    iconClassName?: string;
  } & Omit<React.ComponentPropsWithoutRef<typeof Button>, "variant" | "size">
>(({ className, iconClassName, ...props }, ref) => (
  <Button
    ref={ref}
    variant="text"
    tabIndex={-1}
    size="xs"
    className={cn(
      "mb-0 opacity-0 group-hover:opacity-100 transition-opacity",
      className,
    )}
    aria-label="More options"
    {...props}
  >
    <MoreVerticalIcon className={cn("w-4 h-4", iconClassName)} />
  </Button>
));
MoreActionsButton.displayName = "MoreActionsButton";

/** Standard class string for icons inside dropdown menu items. */
export const MENU_ITEM_ICON_CLASS = "h-3.5 w-3.5 mr-2";
