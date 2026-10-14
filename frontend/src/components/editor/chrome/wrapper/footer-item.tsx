/* Copyright 2026 Marimo. All rights reserved. */

import type React from "react";
import { Slot as SlotPrimitive } from "radix-ui";
import { forwardRef } from "react";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";

type FooterItemProps = {
  selected: boolean;
  tooltip: React.ReactNode;
  asChild?: boolean;
} & React.HTMLAttributes<HTMLDivElement>;

export const FooterItem: React.FC<FooterItemProps> = forwardRef<
  HTMLDivElement,
  FooterItemProps
>(
  (
    { children, tooltip, selected, className, asChild = false, ...rest },
    ref,
  ) => {
    const Component = asChild ? SlotPrimitive.Slot : "div";
    const content = (
      <Component
        ref={ref}
        className={cn(
          "h-full flex items-center p-2 text-sm shadow-inset font-mono cursor-pointer rounded",
          !selected && "hover:bg-(--sage-3)",
          selected && "bg-(--sage-4)",
          className,
        )}
        {...rest}
      >
        {children}
      </Component>
    );

    if (tooltip) {
      return (
        <Tooltip content={tooltip} side="top" delayDuration={200}>
          {content}
        </Tooltip>
      );
    }

    return content;
  },
);

FooterItem.displayName = "FooterItem";
