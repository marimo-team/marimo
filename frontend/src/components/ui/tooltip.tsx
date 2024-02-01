/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

import { cn } from "@/utils/cn";

const TooltipProvider = TooltipPrimitive.Provider;

const TooltipRoot = TooltipPrimitive.Root;

const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <TooltipPrimitive.Content
    ref={ref}
    sideOffset={sideOffset}
    className={cn(
      "z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-xs data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1",
      className,
    )}
    {...props}
  />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

const Tooltip: React.FC<
  {
    content: React.ReactNode;
    usePortal?: boolean;
    children: React.ReactNode;
    side?: TooltipPrimitive.TooltipContentProps["side"];
  } & React.ComponentPropsWithoutRef<typeof TooltipRoot>
> = ({ content, children, usePortal = true, side, ...rootProps }) => (
  <TooltipRoot disableHoverableContent={true} {...rootProps}>
    <TooltipTrigger asChild={true}>{children}</TooltipTrigger>
    {usePortal ? (
      <TooltipPrimitive.TooltipPortal>
        <TooltipContent side={side}>{content}</TooltipContent>
      </TooltipPrimitive.TooltipPortal>
    ) : (
      <TooltipContent side={side}>{content}</TooltipContent>
    )}
  </TooltipRoot>
);

export {
  Tooltip,
  TooltipRoot,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
};
