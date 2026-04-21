/* Copyright 2026 Marimo. All rights reserved. */

import {
  EyeOffIcon,
  LayoutTemplateIcon,
  type LucideIcon,
  Rows2Icon,
  SparklesIcon,
} from "lucide-react";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import type {
  SlidesLayout,
  SlideType,
} from "../editor/renderers/slides-layout/types";

export const DEFAULT_SLIDE_TYPE: SlideType = "slide";

interface SlideTypeOption {
  value: SlideType;
  label: string;
  description: string;
  Icon: LucideIcon;
}

const SLIDE_TYPE_OPTIONS: SlideTypeOption[] = [
  {
    value: "slide",
    label: "Slide",
    description:
      "A new top-level slide. Advances horizontally with the right arrow.",
    Icon: LayoutTemplateIcon,
  },
  {
    value: "sub-slide",
    label: "Sub-slide",
    description:
      "Stacks vertically under the previous slide. Reached with the down arrow.",
    Icon: Rows2Icon,
  },
  {
    value: "fragment",
    label: "Fragment",
    description: "Reveals step-by-step on the current slide without advancing.",
    Icon: SparklesIcon,
  },
  {
    value: "skip",
    label: "Skip",
    description:
      "Hidden from the presentation. Still visible here in the editor.",
    Icon: EyeOffIcon,
  },
];

export const SlidesForm = ({
  layout,
  setLayout,
  cellId,
}: {
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  cellId: CellId;
}) => {
  const currentSlideType: SlideType =
    layout.cells.get(cellId)?.type ?? DEFAULT_SLIDE_TYPE;

  const handleSlideTypeChange = (value: SlideType) => {
    const existingConfig = layout.cells.get(cellId);
    const newCells = new Map(layout.cells);
    newCells.set(cellId, { ...existingConfig, type: value });
    setLayout({
      ...layout,
      cells: newCells,
    });
  };

  return (
    <div className="flex flex-col gap-3 p-3">
      <span className="font-semibold text-sm">Slide type</span>
      <div
        role="radiogroup"
        aria-label="Slide type"
        className="flex flex-col gap-1.5"
      >
        {SLIDE_TYPE_OPTIONS.map(({ value, label, description, Icon }) => {
          const isSelected = currentSlideType === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => handleSlideTypeChange(value)}
              className={cn(
                "group text-left rounded-md border p-2.5 transition-colors",
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border/60 bg-background hover:bg-accent/50 hover:border-border",
              )}
            >
              <div className="flex items-start gap-2.5">
                <span
                  className={cn(
                    "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded",
                    isSelected
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground group-hover:text-foreground",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </span>
                <div>
                  <p className="text-sm leading-tight">{label}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {description}
                  </p>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};
