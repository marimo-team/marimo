/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import {
  CELL_CHROME_VERTICAL_GAP,
  type ChromeRailPlacement,
} from "./chrome-placement";

interface CellChromeRailProps {
  placement: ChromeRailPlacement;
  className?: string;
  children: React.ReactNode;
}

/** Absolutely positioned vertical stack for cell chrome controls. */
export const CellChromeRail: React.FC<CellChromeRailProps> = ({
  placement,
  className,
  children,
}) => {
  return (
    <div
      className={cn(
        "absolute flex flex-col z-20 print:hidden",
        CELL_CHROME_VERTICAL_GAP,
        placement.className,
        className,
      )}
    >
      {children}
    </div>
  );
};

interface CellChromeItemProps extends React.ComponentProps<typeof Button> {
  children: React.ReactNode;
}

/** One icon button in a chrome rail, with shared hover-action behavior. */
export const CellChromeItem: React.FC<CellChromeItemProps> = ({
  className,
  children,
  size = "xs",
  variant = "text",
  ...props
}) => {
  return (
    <Button
      size={size}
      variant={variant}
      className={cn("hover-action", className)}
      {...props}
    >
      {children}
    </Button>
  );
};
