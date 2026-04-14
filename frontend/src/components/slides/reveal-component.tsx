/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect } from "react";
import { ExpandIcon } from "lucide-react";
import { Deck, Slide } from "@revealjs/react";
import { Slide as CellOutputSlide } from "@/components/slides/slide";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import type { RevealApi } from "reveal.js";
import { Events } from "@/utils/events";

import "./slides.css";
import "./reveal-slides.css";

const RevealSlidesComponent = ({
  cellsWithOutput,
  activeIndex,
  onSlideChange,
  deckRef,
}: {
  cellsWithOutput: (CellRuntimeState & CellData)[];
  activeIndex?: number;
  onSlideChange?: (index: number) => void;
  deckRef: React.RefObject<RevealApi | null>;
}) => {
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
    <div className="group relative h-full w-full flex-1">
      <Deck
        deckRef={deckRef}
        className="relative w-full h-full border rounded bg-background mo-slides-theme prose-slides"
        style={{ height: "100%" }}
        config={{
          embedded: true, // Avoid styles leaking out
          overview: false,
          width: "100%",
          height: "100%", // Both style and config height are needed to ensure the deck is full height
          center: false, // We are handling this manually
          minScale: 1,
          maxScale: 1,
          // Only enable keyboard controls when not focused on an input
          keyboardCondition: (event: KeyboardEvent) => {
            return !Events.fromInput(event);
          },
        }}
        onSlideChange={() => {
          const deck = deckRef.current;
          if (deck) {
            onSlideChange?.(deck.getIndices().h);
            // Trigger resize so vega-embed re-measures container width
            if (deck.getCurrentSlide()?.querySelector("marimo-vega")) {
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
              <div className="mo-slide-content" style={{ margin: "auto 0" }}>
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
          variant="ghost"
          size="icon"
          className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-70 text-muted-foreground transition-opacity h-7 w-7"
          onClick={() => {
            deckRef.current?.getViewportElement()?.requestFullscreen();
          }}
        >
          <ExpandIcon className="h-4 w-4" />
        </Button>
      </Tooltip>
    </div>
  );
};

export default RevealSlidesComponent;
