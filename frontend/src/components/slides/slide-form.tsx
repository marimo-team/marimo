/* Copyright 2026 Marimo. All rights reserved. */

import {
  EyeOffIcon,
  LayoutTemplateIcon,
  type LucideIcon,
  Rows2Icon,
  SparklesIcon,
} from "lucide-react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
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
      <RadioGroup
        aria-label="Slide type"
        value={currentSlideType}
        onValueChange={(value) => handleSlideTypeChange(value as SlideType)}
        className="flex flex-col gap-1.5"
      >
        {SLIDE_TYPE_OPTIONS.map(({ value, label, description, Icon }) => {
          const isSelected = currentSlideType === value;
          return (
            <RadioGroupItem
              key={value}
              value={value}
              className={cn(
                "group h-auto w-full text-left rounded-md p-2.5 transition-colors shadow-none! border",
                "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isSelected
                  ? "border-primary bg-primary/5"
                  : "border-border bg-background hover:bg-accent/50 hover:border-foreground/30",
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
                  <p
                    className={cn(
                      "text-sm font-medium leading-tight",
                      isSelected ? "text-primary" : "text-foreground",
                    )}
                  >
                    {label}
                  </p>
                  <p className="mt-0.5 text-xs text-foreground/70">
                    {description}
                  </p>
                </div>
              </div>
            </RadioGroupItem>
          );
        })}
      </RadioGroup>
    </div>
  );
};
