/* Copyright 2024 Marimo. All rights reserved. */
import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

import { cn } from "@/utils/cn";
import {
  TooltipContent,
  TooltipProvider,
  TooltipRoot,
  TooltipTrigger,
} from "./tooltip";
import { useBoolean } from "../../hooks/useBoolean";
import { TooltipPortal } from "@radix-ui/react-tooltip";

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => {
  const [open, openActions] = useBoolean(false);

  return (
    <SliderPrimitive.Root
      ref={ref}
      className={cn(
        "relative flex w-full touch-none select-none items-center hover:cursor-pointer",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-2 w-full grow overflow-hidden rounded-full bg-slate-200 dark:bg-accent/60">
        <SliderPrimitive.Range className="absolute h-full bg-blue-500 dark:bg-primary" />
      </SliderPrimitive.Track>
      <TooltipProvider>
        <TooltipRoot delayDuration={0} open={open}>
          <TooltipTrigger asChild={true}>
            <SliderPrimitive.Thumb
              className="block h-4 w-4 rounded-full shadow-xsSolid border border-blue-500 dark:border-primary dark:bg-accent bg-white hover:bg-blue-300 focus:bg-blue-300 transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
              onFocus={openActions.setTrue}
              onBlur={openActions.setFalse}
              onMouseEnter={openActions.setTrue}
              onMouseLeave={openActions.setFalse}
            />
          </TooltipTrigger>
          <TooltipPortal>
            {props.value != null && props.value.length === 1 && (
              <TooltipContent key={props.value[0]}>
                {props.value[0]}
              </TooltipContent>
            )}
          </TooltipPortal>
        </TooltipRoot>
      </TooltipProvider>
    </SliderPrimitive.Root>
  );
});
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
