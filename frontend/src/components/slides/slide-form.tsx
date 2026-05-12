/* Copyright 2026 Marimo. All rights reserved. */

import {
  EyeOffIcon,
  LayoutTemplateIcon,
  type LucideIcon,
  Rows2Icon,
  CookieIcon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
  KeyboardIcon,
} from "lucide-react";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import type {
  DeckTransition,
  SlidesLayout,
  SlideType,
} from "../editor/renderers/slides-layout/types";
import { useState } from "react";
import { Tooltip } from "../ui/tooltip";
import { Button } from "../ui/button";
import { Kbd } from "../ui/kbd";
import type { RuntimeCell } from "@/core/cells/types";

export const DEFAULT_SLIDE_TYPE: SlideType = "slide";
export const DEFAULT_DECK_TRANSITION: DeckTransition = "slide";
const COLLAPSED_CONFIG_WIDTH = 36;

export interface SlideTypeOption {
  value: SlideType;
  label: string;
  description: string;
  Icon: LucideIcon;
}

export const SLIDE_TYPE_OPTIONS: readonly SlideTypeOption[] = [
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
    Icon: CookieIcon,
  },
  {
    value: "skip",
    label: "Skip",
    description:
      "Hidden from the presentation. Still visible here in the editor.",
    Icon: EyeOffIcon,
  },
];

/**
 * Lookup form of {@link SLIDE_TYPE_OPTIONS} for O(1) access by `SlideType`.
 */
export const SLIDE_TYPE_OPTIONS_BY_VALUE: Readonly<
  Record<SlideType, SlideTypeOption>
> = Object.fromEntries(
  SLIDE_TYPE_OPTIONS.map((option) => [option.value, option]),
) as Record<SlideType, SlideTypeOption>;

interface DeckTransitionOption {
  value: DeckTransition;
  label: string;
  description: string;
}

const DECK_TRANSITION_OPTIONS: DeckTransitionOption[] = [
  { value: "none", label: "None", description: "No animation between slides." },
  { value: "fade", label: "Fade", description: "Cross-fade between slides." },
  {
    value: "slide",
    label: "Slide",
    description: "Slides move horizontally / vertically.",
  },
  {
    value: "convex",
    label: "Convex",
    description: "Rotate with a convex curve.",
  },
  {
    value: "concave",
    label: "Concave",
    description: "Rotate with a concave curve.",
  },
  { value: "zoom", label: "Zoom", description: "Zoom into the next slide." },
];

const SlidesForm = ({
  layout,
  setLayout,
  cellId,
}: {
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  cellId: CellId;
}) => {
  return (
    <Tabs defaultValue="slide" className="flex flex-col flex-1 p-3 gap-3">
      <TabsList className="grid grid-cols-2">
        <TabsTrigger value="slide">Slide</TabsTrigger>
        <TabsTrigger value="deck">Deck</TabsTrigger>
      </TabsList>
      <TabsContent value="slide" className="mt-0 flex-1">
        <SlideConfigForm
          layout={layout}
          setLayout={setLayout}
          cellId={cellId}
        />
      </TabsContent>
      <TabsContent value="deck" className="mt-0 flex-1">
        <DeckConfigForm layout={layout} setLayout={setLayout} />
      </TabsContent>
      <hr />
      <KeyboardTips />
    </Tabs>
  );
};

const KEYBOARD_TIPS: { keys: string[]; description: string }[] = [
  { keys: ["F"], description: "Enter fullscreen" },
  { keys: ["C"], description: "Toggle code editor" },
];

const KEYBOARD_SHORTCUTS_URL =
  "https://vlaaad.github.io/reveal/keyboard-shortcuts";

const KeyboardTips = () => {
  return (
    <div className="flex flex-col gap-2 text-xs text-muted-foreground">
      <div className="flex items-center gap-1.5 font-medium text-foreground/80">
        <KeyboardIcon className="h-3.5 w-3.5" />
        <span>Shortcuts</span>
      </div>
      <ul className="flex flex-col gap-1.5">
        {KEYBOARD_TIPS.map(({ keys, description }) => (
          <li key={description} className="flex items-center justify-between">
            <span>{description}</span>
            <span className="flex gap-1">
              {keys.map((key) => (
                <Kbd key={key}>{key}</Kbd>
              ))}
            </span>
          </li>
        ))}
      </ul>
      <a
        href={KEYBOARD_SHORTCUTS_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="text-link hover:underline"
      >
        See all shortcuts
      </a>
    </div>
  );
};

const SlideConfigForm = ({
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
    <div className="flex flex-col gap-3">
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

const DeckConfigForm = ({
  layout,
  setLayout,
}: {
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
}) => {
  const currentTransition: DeckTransition =
    layout.deck?.transition ?? DEFAULT_DECK_TRANSITION;
  const activeDescription = DECK_TRANSITION_OPTIONS.find(
    (opt) => opt.value === currentTransition,
  )?.description;

  const handleTransitionChange = (value: DeckTransition) => {
    setLayout({
      ...layout,
      deck: { ...layout.deck, transition: value },
    });
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="deck-transition"
          className="font-semibold text-sm text-foreground"
        >
          Transition
        </label>
        <Select
          value={currentTransition}
          onValueChange={(value) =>
            handleTransitionChange(value as DeckTransition)
          }
        >
          <SelectTrigger id="deck-transition" aria-label="Slide transition">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DECK_TRANSITION_OPTIONS.map(({ value, label }) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {activeDescription && (
          <p className="text-xs text-foreground/70">{activeDescription}</p>
        )}
      </div>
    </div>
  );
};

export const SlideSidebar = ({
  configWidth,
  layout,
  setLayout,
  activeConfigCell,
}: {
  configWidth: number;
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  activeConfigCell?: RuntimeCell;
}) => {
  const [isConfigOpen, setIsConfigOpen] = useState(false);

  return (
    <aside
      className="h-full flex flex-col border-l border-border/60 bg-muted/20 transition-[width] duration-200 ease-out overflow-hidden"
      style={{
        width: isConfigOpen ? configWidth : COLLAPSED_CONFIG_WIDTH,
      }}
      aria-label="Slide configuration"
      // Prevent keys from bubbling up to reveal.js's document-level keydown listener and moving the deck.
      onKeyDown={(e) => e.stopPropagation()}
    >
      <header
        className={cn(
          "flex items-center h-9 shrink-0 border-b border-border/60",
          isConfigOpen ? "justify-between px-2" : "justify-center px-0",
        )}
      >
        {isConfigOpen && (
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground pl-1">
            Configuration
          </span>
        )}
        <Tooltip content={isConfigOpen ? "Collapse panel" : "Expand panel"}>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-muted-foreground hover:text-foreground"
            onClick={() => setIsConfigOpen(!isConfigOpen)}
            aria-expanded={isConfigOpen}
            aria-controls="slide-config-panel"
          >
            {isConfigOpen ? (
              <PanelRightCloseIcon className="h-4 w-4" />
            ) : (
              <PanelRightOpenIcon className="h-4 w-4" />
            )}
          </Button>
        </Tooltip>
      </header>

      {isConfigOpen && (
        <div
          id="slide-config-panel"
          className="flex-1 overflow-y-auto overflow-x-hidden"
        >
          {activeConfigCell ? (
            <SlidesForm
              layout={layout}
              setLayout={setLayout}
              cellId={activeConfigCell.id}
            />
          ) : (
            <div className="flex flex-col gap-1.5 p-3 text-xs text-muted-foreground">
              <span className="font-semibold text-sm text-foreground">
                No slides yet
              </span>
              <p>
                Run a cell that produces output to add it to the deck. Slide
                settings will appear here once a slide is selected.
              </p>
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
