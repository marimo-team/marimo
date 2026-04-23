/* Copyright 2026 Marimo. All rights reserved. */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  Fragment as ReactFragment,
} from "react";
import useEvent from "react-use-event-hook";
import {
  ExpandIcon,
  EyeOffIcon,
  PanelRightCloseIcon,
  PanelRightOpenIcon,
} from "lucide-react";
import { Deck, Fragment, Slide, Stack } from "@revealjs/react";
import { Slide as CellOutputSlide } from "@/components/slides/slide";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import type { CellData, CellRuntimeState } from "@/core/cells/types";
import type { RevealApi, RevealConfig } from "reveal.js";
import { Events } from "@/utils/events";
import { Logger } from "@/utils/Logger";
import "./slides.css";
import "./reveal-slides.css";
import type { SlidesLayout } from "../editor/renderers/slides-layout/types";
import {
  buildSlideIndices,
  composeSlides,
  computeDeckNavigation,
  resolveActiveCellIndex,
  type ComposedSubslide,
} from "./compose-slides";
import {
  DEFAULT_DECK_TRANSITION,
  DEFAULT_SLIDE_TYPE,
  SlidesForm,
} from "./slide-form";
import type { AppMode } from "@/core/mode";

const ASPECT_RATIO = 16 / 9;
const COLLAPSED_CONFIG_WIDTH = 36;

type RuntimeCell = CellRuntimeState & CellData;

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

const SubslideView = ({
  subslide,
}: {
  subslide: ComposedSubslide<RuntimeCell>;
}) => (
  <Slide>
    <div className="h-full w-full overflow-auto flex">
      <div className="mo-slide-content" style={{ margin: "auto 20px" }}>
        {subslide.blocks.map((block, i) => {
          const rendered = block.cells.map((cell) => (
            <CellOutputSlide
              key={cell.id}
              cellId={cell.id}
              status={cell.status}
              output={cell.output}
            />
          ));
          if (block.isFragment) {
            return (
              <Fragment key={i} as="div">
                {rendered}
              </Fragment>
            );
          }
          return <ReactFragment key={i}>{rendered}</ReactFragment>;
        })}
      </div>
    </div>
  </Slide>
);

const RevealSlidesComponent = ({
  cellsWithOutput,
  layout,
  setLayout,
  activeIndex,
  onSlideChange,
  deckRef,
  mode,
  configWidth = 300, // px
}: {
  cellsWithOutput: RuntimeCell[];
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  activeIndex?: number;
  onSlideChange?: (index: number) => void;
  deckRef: React.RefObject<RevealApi | null>;
  mode: AppMode;
  configWidth?: number;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { width, height } = useSlideDimensions(containerRef);
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const activeCell =
    activeIndex != null ? cellsWithOutput[activeIndex] : undefined;
  // Fall back to the first cell so the config panel has something to edit
  // while the deck is still settling on an initial slide. This can still be
  // `undefined` when the deck is empty; that case is handled below.
  const activeConfigCell = activeCell ?? cellsWithOutput[0];

  const composition = useMemo(
    () =>
      composeSlides({
        cells: cellsWithOutput,
        getType: (cell) =>
          layout.cells.get(cell.id)?.type ?? DEFAULT_SLIDE_TYPE,
      }),
    [cellsWithOutput, layout.cells],
  );

  // Skip cells are dropped from the composed deck to match reveal.js
  // semantics. When the user selects a skip cell in the minimap we render an
  // editor-only preview on top of the deck; the deck itself stays put.
  const skippedPreviewCell =
    activeCell && layout.cells.get(activeCell.id)?.type === "skip"
      ? activeCell
      : null;

  const { cellToTarget, targetToCellIndex } = useMemo(
    () =>
      buildSlideIndices({
        composition,
        cells: cellsWithOutput,
        getId: (c) => c.id,
      }),
    [composition, cellsWithOutput],
  );

  const deckTransition = layout.deck?.transition ?? DEFAULT_DECK_TRANSITION;
  const revealConfig: RevealConfig = useMemo(
    () => ({
      embedded: true,
      width,
      height,
      center: false,
      minScale: 0.2,
      maxScale: 2,
      transition: deckTransition,
      keyboardCondition: (event: KeyboardEvent) => !Events.fromInput(event),
    }),
    [width, height, deckTransition],
  );

  useEffect(() => {
    const deck = deckRef.current;
    if (deck == null || activeCell == null) {
      return;
    }
    const target = cellToTarget.get(activeCell.id);
    if (!target) {
      return;
    }
    const next = computeDeckNavigation(deck.getIndices(), target);
    if (next) {
      deck.slide(next.h, next.v, next.f);
    }
  }, [activeCell, cellToTarget, deckRef]);

  // Report the current cell index to the parent component
  const reportCurrentCell = useEvent(() => {
    const deck = deckRef.current;
    if (!deck) {
      return;
    }
    const flatIndex = resolveActiveCellIndex(
      targetToCellIndex,
      deck.getIndices(),
    );
    if (flatIndex != null) {
      onSlideChange?.(flatIndex);
    }
  });

  return (
    <div className="flex-1 min-w-0 flex flex-row gap-3">
      <div
        ref={containerRef}
        className="flex-1 min-w-0 flex items-center justify-center overflow-hidden"
      >
        <div className="group relative" style={{ width, height }}>
          <Deck
            deckRef={deckRef}
            className="aspect-video w-full overflow-hidden border rounded bg-background mo-slides-theme prose-slides"
            config={revealConfig}
            onSlideChange={() => {
              reportCurrentCell();
              const deck = deckRef.current;
              // Trigger resize so vega-embed re-measures container width
              if (
                deck
                  ?.getCurrentSlide()
                  ?.querySelector(".vega-embed, marimo-vega")
              ) {
                requestAnimationFrame(() => {
                  window.dispatchEvent(new Event("resize"));
                });
              }
            }}
            onFragmentShown={reportCurrentCell}
            onFragmentHidden={reportCurrentCell}
          >
            {composition.stacks.map((stack, i) => {
              if (stack.subslides.length === 1) {
                return <SubslideView key={i} subslide={stack.subslides[0]} />;
              }
              return (
                <Stack key={i}>
                  {stack.subslides.map((sub, j) => (
                    <SubslideView key={j} subslide={sub} />
                  ))}
                </Stack>
              );
            })}
          </Deck>
          {skippedPreviewCell && (
            <div
              className="absolute inset-0 z-10 border rounded bg-background flex flex-col overflow-hidden"
              aria-label="Skipped in presentation"
            >
              <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/40">
                <EyeOffIcon className="h-3.5 w-3.5" />
                <span>Skipped in presentation</span>
              </div>
              <div className="flex-1 overflow-auto flex">
                <div
                  className="mo-slide-content"
                  style={{ margin: "auto 20px" }}
                >
                  <CellOutputSlide
                    cellId={skippedPreviewCell.id}
                    status={skippedPreviewCell.status}
                    output={skippedPreviewCell.output}
                  />
                </div>
              </div>
            </div>
          )}
          <Tooltip content="Fullscreen (F)">
            <Button
              data-testid="marimo-plugin-slides-fullscreen"
              variant="ghost"
              size="icon"
              className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-70 text-muted-foreground transition-opacity h-7 w-7"
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
      </div>

      {mode !== "read" && (
        <aside
          className="h-full flex flex-col border-l border-border/60 bg-muted/20 transition-[width] duration-200 ease-out overflow-hidden"
          style={{
            width: isConfigOpen ? configWidth : COLLAPSED_CONFIG_WIDTH,
          }}
          aria-label="Slide configuration"
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
      )}
    </div>
  );
};

export default RevealSlidesComponent;
