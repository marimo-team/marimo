/* Copyright 2026 Marimo. All rights reserved. */

import * as SliderPrimitive from "@radix-ui/react-slider";
import * as React from "react";
import { useLocale } from "react-aria";
import { cn } from "@/utils/cn";
import { prettyScientificNumber } from "@/utils/numbers";
import { useBoolean } from "../../hooks/useBoolean";
import {
  TooltipContent,
  TooltipPortal,
  TooltipProvider,
  TooltipRoot,
  TooltipTrigger,
} from "./tooltip";

const RangeSlider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & {
    valueMap: (sliderValue: number) => number;
    steps?: number[];
  }
>(({ className, valueMap, ...props }, ref) => {
  const [open, openActions] = useBoolean(false);
  const { locale } = useLocale();

  const isDraggingRange = React.useRef(false);
  const dragStartX = React.useRef(0);
  const dragStartY = React.useRef(0);
  const dragStartValue = React.useRef<number[]>([]);
  const currentDragValue = React.useRef<number[]>([]);
  const rootRef =
    React.useRef<React.ElementRef<typeof SliderPrimitive.Root>>(null);
  const trackRef = React.useRef<HTMLSpanElement>(null);
  const dragTrackRect = React.useRef<DOMRect | null>(null);

  const mergedRef = React.useCallback(
    (node: React.ElementRef<typeof SliderPrimitive.Root>) => {
      rootRef.current = node;
      if (typeof ref === "function") {
        ref(node);
      } else if (ref) {
        ref.current = node;
      }
    },
    [ref],
  );

  const handleRangePointerDown = (e: React.PointerEvent<HTMLSpanElement>) => {
    if (!props.value || props.value.length !== 2) {
      return;
    }
    if (props.disabled) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();

    isDraggingRange.current = true;
    dragStartX.current = e.clientX;
    dragStartY.current = e.clientY;
    dragStartValue.current = [...props.value];
    currentDragValue.current = [...props.value];
    dragTrackRect.current = trackRef.current?.getBoundingClientRect() ?? null;

    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const handleRangePointerMove = (e: React.PointerEvent<HTMLSpanElement>) => {
    if (!isDraggingRange.current) {
      return;
    }
    e.stopPropagation();

    const trackRect = dragTrackRect.current;
    if (!trackRect) {
      return;
    }

    const isVertical = props.orientation === "vertical";
    const min = props.min ?? 0;
    const max = props.max ?? 100;
    const totalRange = max - min;

    let delta: number;
    if (isVertical) {
      const trackLength = trackRect.height;
      delta = -((e.clientY - dragStartY.current) / trackLength) * totalRange;
    } else {
      const trackLength = trackRect.width;
      delta = ((e.clientX - dragStartX.current) / trackLength) * totalRange;
    }

    const [origLeft, origRight] = dragStartValue.current;
    const rangeWidth = origRight - origLeft;

    const steps = props.steps;
    const step: number =
      steps && steps.length > 1
        ? Math.min(...steps.slice(1).map((s, i) => s - steps[i]))
        : (props.step ?? 1);
    const snappedDelta = Math.round(delta / step) * step;

    const clampedDelta = Math.max(
      min - origLeft,
      Math.min(max - origRight, snappedDelta),
    );

    const newLeft = origLeft + clampedDelta;
    const newRight = newLeft + rangeWidth;

    currentDragValue.current = [newLeft, newRight];
    props.onValueChange?.([newLeft, newRight]);
  };

  const handleRangePointerUp = (e: React.PointerEvent<HTMLSpanElement>) => {
    if (!isDraggingRange.current) {
      return;
    }
    (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    isDraggingRange.current = false;

    if (currentDragValue.current.length === 2) {
      props.onValueCommit?.(currentDragValue.current);
    }
  };

  return (
    <SliderPrimitive.Root
      ref={mergedRef}
      className={cn(
        "relative flex touch-none select-none hover:cursor-pointer",
        "data-[orientation=horizontal]:w-full data-[orientation=horizontal]:items-center",
        "data-[orientation=vertical]:h-full data-[orientation=vertical]:justify-center",
        "data-disabled:cursor-not-allowed",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track
        ref={trackRef}
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
            "data-disabled:opacity-50",
            "hover:cursor-grab active:cursor-grabbing",
          )}
          onPointerDown={handleRangePointerDown}
          onPointerMove={handleRangePointerMove}
          onPointerUp={handleRangePointerUp}
        />
      </SliderPrimitive.Track>
      <TooltipProvider>
        <TooltipRoot delayDuration={0} open={open}>
          <TooltipTrigger asChild={true}>
            <SliderPrimitive.Thumb
              data-testid="thumb"
              className="block h-4 w-4 rounded-full shadow-xs-solid border border-blue-500 dark:border-primary dark:bg-accent bg-white hover:bg-blue-300 focus:bg-blue-300 transition-colors focus-visible:outline-hidden data-disabled:pointer-events-none data-disabled:opacity-50"
              onFocus={openActions.setTrue}
              onBlur={openActions.setFalse}
              onMouseEnter={openActions.setTrue}
              onMouseLeave={openActions.setFalse}
            />
          </TooltipTrigger>
          <TooltipPortal>
            {props.value != null && props.value.length === 2 && (
              <TooltipContent key={props.value[0]}>
                {prettyScientificNumber(valueMap(props.value[0]), { locale })}
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
              className="block h-4 w-4 rounded-full shadow-xs-solid border border-blue-500 dark:border-primary dark:bg-accent bg-white hover:bg-blue-300 focus:bg-blue-300 transition-colors focus-visible:outline-hidden data-disabled:pointer-events-none data-disabled:opacity-50"
              onFocus={openActions.setTrue}
              onBlur={openActions.setFalse}
              onMouseEnter={openActions.setTrue}
              onMouseLeave={openActions.setFalse}
            />
          </TooltipTrigger>
          <TooltipPortal>
            {props.value != null && props.value.length === 2 && (
              <TooltipContent key={props.value[1]}>
                {prettyScientificNumber(valueMap(props.value[1]), { locale })}
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
