/* Copyright 2024 Marimo. All rights reserved. */

import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import * as React from "react";
import { StyleNamespace } from "@/theme/namespace";
import { cn } from "@/utils/cn";

const TooltipProvider = ({
  delayDuration = 400,
  ...props
}: TooltipPrimitive.TooltipProviderProps) => (
  <TooltipPrimitive.Provider delayDuration={delayDuration} {...props} />
);

const TooltipRoot = TooltipPrimitive.Root;

const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<
  React.ElementRef<typeof TooltipPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <StyleNamespace>
    <TooltipPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 overflow-hidden rounded-md border bg-popover px-3 py-1.5 text-sm text-popover-foreground shadow-xs data-[side=bottom]:slide-in-from-top-1 data-[side=left]:slide-in-from-right-1 data-[side=right]:slide-in-from-left-1 data-[side=top]:slide-in-from-bottom-1",
        className,
      )}
      {...props}
    />
  </StyleNamespace>
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

const Tooltip: React.FC<
  {
    content: React.ReactNode;
    usePortal?: boolean;
    children: React.ReactNode;
    asChild?: boolean;
    side?: TooltipPrimitive.TooltipContentProps["side"];
    tabIndex?: number;
    align?: TooltipPrimitive.TooltipContentProps["align"];
  } & React.ComponentPropsWithoutRef<typeof TooltipRoot>
> = ({
  content,
  children,
  usePortal = true,
  asChild = true,
  tabIndex,
  side,
  align,
  ...rootProps
}) => {
  if (content == null || content === "") {
    return children;
  }

  return (
    <TooltipRoot disableHoverableContent={true} {...rootProps}>
      <TooltipTrigger asChild={asChild} tabIndex={tabIndex}>
        {children}
      </TooltipTrigger>
      {usePortal ? (
        <TooltipPrimitive.TooltipPortal>
          <TooltipContent side={side} align={align}>
            {content}
          </TooltipContent>
        </TooltipPrimitive.TooltipPortal>
      ) : (
        <TooltipContent side={side} align={align}>
          {content}
        </TooltipContent>
      )}
    </TooltipRoot>
  );
};

export {
  Tooltip,
  TooltipRoot,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
};
