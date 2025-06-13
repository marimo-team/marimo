/* Copyright 2024 Marimo. All rights reserved. */

import * as SliderPrimitive from "@radix-ui/react-slider";
import { TooltipPortal } from "@radix-ui/react-tooltip";
import * as React from "react";
import { cn } from "@/utils/cn";
import { prettyScientificNumber } from "@/utils/numbers";
import { useBoolean } from "../../hooks/useBoolean";
import {
  TooltipContent,
  TooltipProvider,
  TooltipRoot,
  TooltipTrigger,
} from "./tooltip";

const RangeSlider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
    valueMap: (sliderValue: number) => number;
  }
>(({ className, valueMap, ...props }, ref) => {
  const [open, openActions] = useBoolean(false);

  return (
    <SliderPrimitive.Root
      ref={ref}
      className={cn(
        "relative flex touch-none select-none hover:cursor-pointer",
        "data-[orientation=horizontal]:w-full data-[orientation=horizontal]:items-center",
        "data-[orientation=vertical]:h-full data-[orientation=vertical]:justify-center",
        "data-[disabled]:cursor-not-allowed",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track
        data-testid="track"
        className={cn(
          "relative grow overflow-hidden rounded-full bg-slate-200 dark:bg-accent/60",
          "data-[orientation=horizontal]:h-2 data-[orientation=horizontal]:w-full",
          "data-[orientation=vertical]:h-full data-[orientation=vertical]:w-2",
        )}
      >
        <SliderPrimitive.Range
          data-testid="range"
          className={cn(
            "absolute bg-blue-500 dark:bg-primary",
            "data-[orientation=horizontal]:h-full",
            "data-[orientation=vertical]:w-full",
            "data-[disabled]:opacity-50",
          )}
        />
      </SliderPrimitive.Track>
      <TooltipProvider>
        <TooltipRoot delayDuration={0} open={open}>
          <TooltipTrigger asChild={true}>
            <SliderPrimitive.Thumb
              data-testid="thumb"
              className="block h-4 w-4 rounded-full shadow-xsSolid border border-blue-500 dark:border-primary dark:bg-accent bg-white hover:bg-blue-300 focus:bg-blue-300 transition-colors focus-visible:outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              onFocus={openActions.setTrue}
              onBlur={openActions.setFalse}
              onMouseEnter={openActions.setTrue}
              onMouseLeave={openActions.setFalse}
            />
          </TooltipTrigger>
          <TooltipPortal>
            {props.value != null && props.value.length === 2 && (
              <TooltipContent key={props.value[0]}>
                {prettyScientificNumber(valueMap(props.value[0]))}
              </TooltipContent>
            )}
          </TooltipPortal>
        </TooltipRoot>
      </TooltipProvider>
      <TooltipProvider>
        <TooltipRoot delayDuration={0} open={open}>
          <TooltipTrigger asChild={true}>
            <SliderPrimitive.Thumb
              data-testid="thumb"
              className="block h-4 w-4 rounded-full shadow-xsSolid border border-blue-500 dark:border-primary dark:bg-accent bg-white hover:bg-blue-300 focus:bg-blue-300 transition-colors focus-visible:outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
              onFocus={openActions.setTrue}
              onBlur={openActions.setFalse}
              onMouseEnter={openActions.setTrue}
              onMouseLeave={openActions.setFalse}
            />
          </TooltipTrigger>
          <TooltipPortal>
            {props.value != null && props.value.length === 2 && (
              <TooltipContent key={props.value[1]}>
                {prettyScientificNumber(valueMap(props.value[1]))}
              </TooltipContent>
            )}
          </TooltipPortal>
        </TooltipRoot>
      </TooltipProvider>
    </SliderPrimitive.Root>
  );
});

RangeSlider.displayName = SliderPrimitive.Root.displayName;

export { RangeSlider };
