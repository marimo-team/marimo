/* Copyright 2024 Marimo. All rights reserved. */

import * as PopoverPrimitive from "@radix-ui/react-popover";
import * as React from "react";
import { StyleNamespace } from "@/theme/namespace";
import { cn } from "@/utils/cn";
import { withFullScreenAsRoot } from "./fullscreen";

const Popover = PopoverPrimitive.Root;

const PopoverTrigger = PopoverPrimitive.Trigger;
const PopoverPortal = withFullScreenAsRoot(PopoverPrimitive.Portal);
const PopoverClose = PopoverPrimitive.Close;

const PopoverContent = React.forwardRef<
  React.ElementRef<typeof PopoverPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof PopoverPrimitive.Content> & {
    portal?: boolean;
    scrollable?: boolean;
  }
>(
  (
    {
      className,
      align = "center",
      sideOffset = 4,
      portal = true,
      scrollable = false,
      ...props
    },
    ref,
  ) => {
    const content = (
      <StyleNamespace>
        <PopoverPrimitive.Content
          ref={ref}
          align={align}
          sideOffset={sideOffset}
          className={cn(
            "z-50 w-72 rounded-md border bg-popover p-4 text-popover-foreground shadow-md outline-none animate-in data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
            className,
            scrollable && "overflow-auto",
          )}
          style={{
            ...props.style,
            maxHeight: scrollable
              ? "calc(var(--radix-popover-content-available-height) - 30px)"
              : undefined,
          }}
          {...props}
        />
      </StyleNamespace>
    );
    if (portal) {
      return <PopoverPortal>{content}</PopoverPortal>;
    }

    return content;
  },
);
PopoverContent.displayName = PopoverPrimitive.Content.displayName;

export { Popover, PopoverTrigger, PopoverContent, PopoverClose };
