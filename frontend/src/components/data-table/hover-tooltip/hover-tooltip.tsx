/* Copyright 2026 Marimo. All rights reserved. */
import {
  TooltipContent,
  TooltipPortal,
  TooltipRoot,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { HoverTooltipState } from "./use-table-hover-tooltip";

interface HoverTooltipProps {
  state: HoverTooltipState | null;
  contentId: string;
  onClose: () => void;
}

/**
 * A single radix tooltip whose anchor is repositioned to the hovered cell.
 * Rendering one instance per table (instead of one per cell) keeps the cost
 * constant regardless of how many cells are on screen.
 */
export const HoverTooltip = ({
  state,
  contentId,
  onClose,
}: HoverTooltipProps) => {
  return (
    <TooltipRoot
      open={state != null}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
      delayDuration={0}
      disableHoverableContent={true}
    >
      <TooltipTrigger asChild={true}>
        <div
          aria-hidden={true}
          style={{
            position: "fixed",
            top: state?.rect.top ?? 0,
            left: state?.rect.left ?? 0,
            width: state?.rect.width ?? 0,
            height: state?.rect.height ?? 0,
            pointerEvents: "none",
          }}
        />
      </TooltipTrigger>
      <TooltipPortal>
        <TooltipContent id={contentId}>{state?.content}</TooltipContent>
      </TooltipPortal>
    </TooltipRoot>
  );
};
