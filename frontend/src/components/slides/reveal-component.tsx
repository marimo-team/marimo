/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import { ChevronRightIcon, ExpandIcon, SettingsIcon } from "lucide-react";
import { Deck, Slide } from "@revealjs/react";
import { Slide as CellOutputSlide } from "@/components/slides/slide";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import type { RevealApi } from "reveal.js";
import { Events } from "@/utils/events";
import { Logger } from "@/utils/Logger";
import {
  Select,
  SelectItem,
  SelectContent,
  SelectTrigger,
  SelectValue,
} from "../ui/select";
import "./slides.css";
import "./reveal-slides.css";
import type {
  SlideType,
  SlidesLayout,
} from "../editor/renderers/slides-layout/types";
import type { CellId } from "@/core/cells/ids";

const ASPECT_RATIO = 16 / 9;
const COLLAPSED_CONFIG_WIDTH = 32;
const DEFAULT_SLIDE_TYPE: SlideType = "slide";

function useSlideDimensions(ref: React.RefObject<HTMLDivElement | null>) {
  const [dims, setDims] = useState({ width: 960, height: 540 });

  useEffect(() => {
    const el = ref.current;
    if (!el) {
      return;
    }

    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width <= 0 || height <= 0) {
        return;
      }
      const fitWidth = Math.min(width, height * ASPECT_RATIO);
      const fitHeight = fitWidth / ASPECT_RATIO;
      setDims({
        width: Math.round(fitWidth),
        height: Math.round(fitHeight),
      });
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);

  return dims;
}

const RevealSlidesComponent = ({
  cellsWithOutput,
  layout,
  setLayout,
  activeIndex,
  onSlideChange,
  deckRef,
  configWidth = 300, // px
}: {
  cellsWithOutput: (CellRuntimeState & CellData)[];
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  activeIndex?: number;
  onSlideChange?: (index: number) => void;
  deckRef: React.RefObject<RevealApi | null>;
  configWidth?: number;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { width, height } = useSlideDimensions(containerRef);
  const [isConfigOpen, setIsConfigOpen] = useState(true);
  const activeCellId = cellsWithOutput[activeIndex ?? 0]?.id;

  useEffect(() => {
    const deck = deckRef.current;
    if (deck == null || activeIndex == null) {
      return;
    }
    const { h } = deck.getIndices();
    if (h !== activeIndex) {
      deck.slide(activeIndex);
    }
  }, [activeIndex, deckRef]);

  return (
    <div
      ref={containerRef}
      className="relative h-full w-full flex-1 flex flex-row gap-3 items-center"
    >
      <div className="group relative flex-1">
        <Deck
          deckRef={deckRef}
          className="aspect-video overflow-hidden h-full border rounded bg-background mo-slides-theme prose-slides"
          config={{
            embedded: true,
            width,
            height,
            center: false,
            minScale: 0.2,
            maxScale: 2,
            keyboardCondition: (event: KeyboardEvent) => {
              return !Events.fromInput(event);
            },
          }}
          onSlideChange={() => {
            const deck = deckRef.current;
            if (deck) {
              onSlideChange?.(deck.getIndices().h);
              // Trigger resize so vega-embed re-measures container width
              if (
                deck
                  .getCurrentSlide()
                  ?.querySelector(".vega-embed, marimo-vega")
              ) {
                requestAnimationFrame(() => {
                  window.dispatchEvent(new Event("resize"));
                });
              }
            }
          }}
        >
          {cellsWithOutput.map((cell) => (
            <Slide key={cell.id}>
              <div className="h-full w-full overflow-auto flex">
                <div
                  className="mo-slide-content"
                  style={{ margin: "auto 20px" }}
                >
                  <CellOutputSlide
                    cellId={cell.id}
                    status={cell.status}
                    output={cell.output}
                  />
                </div>
              </div>
            </Slide>
          ))}
        </Deck>
        <Tooltip content="Fullscreen (F)">
          <Button
            data-testid="marimo-plugin-slides-fullscreen"
            variant="ghost"
            size="icon"
            className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-70 text-muted-foreground transition-opacity h-7 w-7"
            onClick={() => {
              deckRef.current
                ?.getViewportElement()
                ?.requestFullscreen()
                .catch((error) => {
                  Logger.error("Failed to request fullscreen", error);
                });
            }}
          >
            <ExpandIcon className="h-4 w-4" />
          </Button>
        </Tooltip>
      </div>

      <div
        className="h-full flex flex-col transition-[width] duration-200 ease-out overflow-hidden -mr-5"
        style={{
          width: isConfigOpen ? configWidth : COLLAPSED_CONFIG_WIDTH,
        }}
      >
        <div className="flex items-center gap-1">
          <Tooltip content={isConfigOpen ? "Collapse" : "Expand"}>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground"
              onClick={() => setIsConfigOpen((v) => !v)}
              aria-expanded={isConfigOpen}
              aria-controls="slide-config-panel"
            >
              {isConfigOpen ? (
                <ChevronRightIcon className="h-4 w-4" />
              ) : (
                <SettingsIcon className="h-4 w-4" />
              )}
            </Button>
          </Tooltip>
          {isConfigOpen && (
            <h2 className="text-md font-semibold flex-1 text-center">
              Slide Configuration
            </h2>
          )}
        </div>

        {isConfigOpen && (
          <SlidesForm
            layout={layout}
            setLayout={setLayout}
            cellId={activeCellId}
          />
        )}
      </div>
    </div>
  );
};

const SlidesForm = ({
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
    <div id="slide-config-panel" className="p-3 mt-5">
      <div className="flex flex-row gap-2 items-center">
        <Select
          value={currentSlideType}
          onValueChange={(value) => {
            handleSlideTypeChange(value as SlideType);
          }}
        >
          <SelectTrigger className="w-32">
            <SelectValue placeholder="Slide Type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="slide">Slide</SelectItem>
            <SelectItem value="sub-slide">Sub-slide</SelectItem>
            <SelectItem value="fragment">Fragment</SelectItem>
            <SelectItem value="skip">Skip</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>
  );
};

export default RevealSlidesComponent;
