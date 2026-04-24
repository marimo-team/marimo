/* Copyright 2026 Marimo. All rights reserved. */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  Fragment as ReactFragment,
} from "react";
import useEvent from "react-use-event-hook";
import { ExpandIcon, EyeOffIcon } from "lucide-react";
import { Deck, Fragment, Slide, Stack } from "@revealjs/react";
import { Slide as CellOutputSlide } from "@/components/slides/slide";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import type { RuntimeCell } from "@/core/cells/types";
import type { RevealApi, RevealConfig } from "reveal.js";
import { useEventListener } from "@/hooks/useEventListener";
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
  resolveDeckNavigationTarget,
  type ComposedSubslide,
} from "./compose-slides";
import {
  DEFAULT_DECK_TRANSITION,
  DEFAULT_SLIDE_TYPE,
  SlideSidebar,
} from "./slide-form";
import type { AppMode } from "@/core/mode";

const ASPECT_RATIO = 16 / 9;

/**
 * reveal.js caches the last visited vertical index on each stack and can
 * resume there on later horizontal navigation. After minimap-driven jumps we
 * want stacks to re-enter from the top instead of reusing stale stack state.
 */
function clearPreviousVerticalIndices(deck: RevealApi) {
  const slidesEl = deck.getSlidesElement();
  if (!slidesEl) {
    return;
  }

  for (const stack of slidesEl.querySelectorAll(
    "section.stack[data-previous-indexv]",
  )) {
    stack.removeAttribute("data-previous-indexv");
  }
}

const FORWARD_NAV_KEYS = new Set([
  " ",
  "Spacebar",
  "ArrowRight",
  "ArrowDown",
  "PageDown",
]);
const BACK_NAV_KEYS = new Set(["ArrowLeft", "ArrowUp", "PageUp"]);

function classifyNavKey(event: KeyboardEvent): 1 | -1 | 0 {
  if (FORWARD_NAV_KEYS.has(event.key)) {
    return 1;
  }
  if (BACK_NAV_KEYS.has(event.key)) {
    return -1;
  }
  return 0;
}

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

/**
 * Trigger a resize event on the window
 * Vega elements need to be re-measured when the container width changes.
 */
function triggerResize(deck: RevealApi | null) {
  if (deck?.getCurrentSlide()?.querySelector(".vega-embed, marimo-vega")) {
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("resize"));
    });
  }
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
  const activeCell =
    activeIndex != null ? cellsWithOutput[activeIndex] : undefined;
  // Fall back to the first cell while the deck settles on an initial slide.
  // Still `undefined` when the deck is empty (handled below).
  const activeConfigCell = activeCell ?? cellsWithOutput.at(0);

  const composition = useMemo(
    () =>
      composeSlides({
        cells: cellsWithOutput,
        getType: (cell) =>
          layout.cells.get(cell.id)?.type ?? DEFAULT_SLIDE_TYPE,
      }),
    [cellsWithOutput, layout.cells],
  );

  // Skip cells aren't part of the composed deck. When one is selected in the
  // minimap we render a preview over the deck and park reveal on a neighboring
  // real slide; keyboard nav while parked is handled below.
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
    if (deck == null) {
      return;
    }
    const target = resolveDeckNavigationTarget({
      activeIndex,
      cells: cellsWithOutput,
      cellToTarget,
      getId: (cell) => cell.id,
    });
    const next = target && computeDeckNavigation(deck.getIndices(), target);
    if (!next) {
      return;
    }
    deck.slide(next.h, next.v, next.f);
    clearPreviousVerticalIndices(deck);
  }, [activeIndex, cellToTarget, cellsWithOutput, deckRef]);

  // Forward the deck's current cell to the parent, except while a skipped
  // preview is parked: every reveal.js event during that window is an echo
  // of the programmatic park (possibly with transient indices), so ignoring
  // them keeps `activeCellId` pinned on the skipped cell.
  const reportCurrentCell = useEvent(() => {
    if (skippedPreviewCell != null) {
      return;
    }
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

  // While parked on a skipped preview, step through minimap order instead of
  // letting reveal.js advance from the parked slide the user can't see.
  const handleParkedNavKey = useEvent((event: KeyboardEvent) => {
    if (!skippedPreviewCell || activeIndex == null) {
      return;
    }
    if (Events.fromInput(event)) {
      return;
    }
    const direction = classifyNavKey(event);
    if (direction === 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    const nextIndex = activeIndex + direction;
    if (nextIndex < 0 || nextIndex >= cellsWithOutput.length) {
      return;
    }
    onSlideChange?.(nextIndex);
  });

  useEventListener(document, "keydown", handleParkedNavKey, { capture: true });

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
              triggerResize(deck);
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
        <SlideSidebar
          configWidth={configWidth}
          layout={layout}
          setLayout={setLayout}
          activeConfigCell={activeConfigCell}
        />
      )}
    </div>
  );
};

export default RevealSlidesComponent;
