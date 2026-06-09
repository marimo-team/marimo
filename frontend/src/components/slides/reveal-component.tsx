/* Copyright 2026 Marimo. All rights reserved. */

import {
  startTransition,
  useEffect,
  useMemo,
  useRef,
  useState,
  Fragment as ReactFragment,
} from "react";
import useEvent from "react-use-event-hook";
import { CodeIcon, ExpandIcon, EyeOffIcon } from "lucide-react";
import { Deck, Fragment, Slide, Stack } from "@revealjs/react";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { Slide as CellOutputSlide } from "@/components/slides/slide";
import { Button } from "@/components/ui/button";
import { useFullScreenElement } from "@/components/ui/fullscreen";
import { Tooltip } from "@/components/ui/tooltip";
import type { CellId } from "@/core/cells/ids";
import type { RuntimeCell } from "@/core/cells/types";
import type { RevealApi, RevealConfig } from "reveal.js";
import { useEventListener } from "@/hooks/useEventListener";
import { Events } from "@/utils/events";
import { Logger } from "@/utils/Logger";
import "./slides.css";
import "./reveal-slides.css";
import type {
  SlideConfig,
  SlidesLayout,
} from "../editor/renderers/slides-layout/types";
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
import {
  SlideCellReadOnlyView,
  SlideCellView,
} from "@/components/slides/slide-cell-view";
import { SlideNotesEditor } from "./slide-notes-editor";
import { buildSubslideNotes, NOTES_DIVIDER } from "./slide-notes";
import { cn } from "@/utils/cn";
import { isIslands } from "@/core/islands/utils";
import { useNotebookCodeAvailable } from "@/core/meta/code-visibility";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { useAtomValue } from "jotai";
import RevealNotes from "reveal.js/plugin/notes";

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

// The speaker view renders this via innerHTML with `white-space: normal`, so
// we materialize `\n` as `<br>` and a lone `---` line as `<hr>`.
const NotesAside = ({ text }: { text: string }) => {
  const lines = text.split("\n");
  return (
    <aside className="notes">
      {lines.map((line, idx) => {
        const isLast = idx === lines.length - 1;
        if (line === NOTES_DIVIDER) {
          return <hr key={idx} />;
        }
        return (
          <ReactFragment key={idx}>
            {line}
            {!isLast && <br />}
          </ReactFragment>
        );
      })}
    </aside>
  );
};

const SubslideView = ({
  subslide,
  showCode,
  isEditable,
  slideConfigs,
}: {
  subslide: ComposedSubslide<RuntimeCell>;
  showCode: boolean;
  isEditable: boolean;
  slideConfigs: ReadonlyMap<CellId, SlideConfig>;
}) => {
  const { slideLevel, cumulativeByBlock } = buildSubslideNotes(
    subslide,
    slideConfigs,
  );

  return (
    <Slide>
      <div className="h-full w-full overflow-auto flex">
        <div
          className={
            showCode
              ? "mo-slide-content flex flex-col gap-3"
              : "mo-slide-content"
          }
          style={{
            margin: "auto 20px",
          }}
        >
          {subslide.blocks.map((block, i) => {
            const rendered = block.cells.map((cell) => {
              if (!showCode) {
                return (
                  <CellOutputSlide
                    key={cell.id}
                    cellId={cell.id}
                    status={cell.status}
                    output={cell.output}
                  />
                );
              }
              return isEditable ? (
                <SlideCellView key={cell.id} cell={cell} />
              ) : (
                <SlideCellReadOnlyView key={cell.id} cell={cell} />
              );
            });
            if (block.isFragment) {
              const cumulative = cumulativeByBlock.get(i);
              return (
                <Fragment key={i} as="div">
                  {rendered}
                  {cumulative && <NotesAside text={cumulative} />}
                </Fragment>
              );
            }
            return <ReactFragment key={i}>{rendered}</ReactFragment>;
          })}
        </div>
      </div>
      {/* Outside any `.fragment`: shown only before any fragment is revealed. */}
      {slideLevel && <NotesAside text={slideLevel} />}
    </Slide>
  );
};

const ParkedPreviewContent = ({
  cell,
  isNoOutputPreview,
  isEditable,
  codeShown,
}: {
  cell: RuntimeCell;
  isNoOutputPreview: boolean;
  isEditable: boolean;
  codeShown: boolean;
}) => {
  if (isNoOutputPreview && isEditable) {
    return <SlideCellView cell={cell} />;
  }
  if (isNoOutputPreview && codeShown) {
    return <SlideCellReadOnlyView cell={cell} />;
  }
  return (
    <CellOutputSlide
      cellId={cell.id}
      status={cell.status}
      output={cell.output}
    />
  );
};

// There is an upstream react bug in dev mode (https://github.com/facebook/react/issues/34840)
// Uncaught SecurityError: Failed to read a named property '$$typeof' from 'Window'
// Happens with cells containing iframes / external content
const RevealSlidesComponent = ({
  slideCells,
  layout,
  setLayout,
  noOutputIds,
  activeIndex,
  onSlideChange,
  mode,
  configWidth, // px
  isEditable = false,
}: {
  slideCells: RuntimeCell[];
  layout: SlidesLayout;
  setLayout: (layout: SlidesLayout) => void;
  noOutputIds: ReadonlySet<CellId>;
  activeIndex?: number;
  onSlideChange?: (index: number) => void;
  mode: AppMode;
  configWidth: number;
  isEditable?: boolean;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const deckRef = useRef<RevealApi | null>(null);
  const { width, height } = useSlideDimensions(containerRef);
  const isFullscreen = useFullScreenElement() != null;

  // Skip the Notes plugin inside reveal's own speaker-view iframes so pressing
  // `S` there doesn't try to spawn another popup.
  const kioskMode = useAtomValue(kioskModeAtom);
  const deckPlugins = useMemo(
    () => (kioskMode ? [] : [RevealNotes]),
    [kioskMode],
  );

  const [showCode, setShowCode] = useState(false);
  const codeAvailable = useNotebookCodeAvailable(slideCells);
  const codeToggleEnabled = !isIslands() && codeAvailable;
  const codeShown = codeToggleEnabled && showCode;

  const activeCell = activeIndex != null ? slideCells[activeIndex] : undefined;
  // Fall back to the first cell while the deck settles on an initial slide.
  // Still `undefined` when the deck is empty (handled below).
  const activeConfigCell = activeCell ?? slideCells.at(0);

  const composition = useMemo(
    () =>
      composeSlides({
        cells: slideCells,
        getType: (cell) =>
          noOutputIds.has(cell.id)
            ? "skip"
            : (layout.cells.get(cell.id)?.type ?? DEFAULT_SLIDE_TYPE),
      }),
    [slideCells, noOutputIds, layout.cells],
  );

  // Skipped and output-less cells aren't part of the composed deck. When one is
  // selected in the minimap we render a preview over the deck and park reveal on
  // a neighboring real slide; keyboard nav while parked is handled below.
  const activeCellSlideType = activeCell
    ? layout.cells.get(activeCell.id)?.type
    : undefined;
  const isNoOutputPreview =
    activeCell != null && noOutputIds.has(activeCell.id);
  const isParkedPreview = activeCellSlideType === "skip" || isNoOutputPreview;
  const parkedPreviewCell = isParkedPreview ? activeCell : null;

  const { cellToTarget, targetToCellIndex } = useMemo(
    () =>
      buildSlideIndices({
        composition,
        cells: slideCells,
        getId: (c) => c.id,
      }),
    [composition, slideCells],
  );

  const deckTransition = layout.deck?.transition ?? DEFAULT_DECK_TRANSITION;
  // Reveal's Notes plugin iframes the deck for the current/upcoming-slide
  // previews. We load the same URL but as a read-only kiosk client with the
  // app chrome hidden, which `<SlidesLayoutRenderer>` interprets the same as
  // read mode (no minimap, sidebar, or notes editor).
  const kioskUrl = useMemo(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("kiosk", "true");
    url.searchParams.set("show-chrome", "false");
    return url.toString();
  }, []);
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
      url: kioskUrl,
    }),
    [width, height, deckTransition, kioskUrl],
  );

  const navigateDeckToActiveCell = useEvent((deck: RevealApi) => {
    const target = resolveDeckNavigationTarget({
      activeIndex,
      cells: slideCells,
      cellToTarget,
      getId: (cell) => cell.id,
    });
    const next = target && computeDeckNavigation(deck.getIndices(), target);
    if (!next) {
      return;
    }
    deck.slide(next.h, next.v, next.f);
    clearPreviousVerticalIndices(deck);
  });

  useEffect(() => {
    const deck = deckRef.current;
    if (deck == null) {
      return;
    }
    navigateDeckToActiveCell(deck);
  }, [activeIndex, cellToTarget, slideCells, navigateDeckToActiveCell]);

  // Toggling code (re)mounts a CodeMirror editor on the active slide. Defer
  // the state update so the button/keypress paints first and the heavier mount
  // can be interrupted by higher-priority work.
  const toggleShowCode = useEvent(() => {
    startTransition(() => setShowCode((value) => !value));
  });

  const handleDeckReady = useEvent((deck: RevealApi) => {
    navigateDeckToActiveCell(deck);
    if (codeToggleEnabled) {
      deck.addKeyBinding(
        { keyCode: 67, key: "C", description: "Toggle code editor" },
        toggleShowCode,
      );
    }

    // Reveal listens for `keydown` on `document` and bails when
    // `document.activeElement` is an input/contenteditable (e.g. the speaker
    // notes textarea below the deck). Park focus on the deck wrapper so arrow
    // keys reliably advance slides without the user having to click first.
    const revealEl = deck.getSlidesElement()?.closest(".reveal");
    if (revealEl instanceof HTMLElement) {
      revealEl.tabIndex = -1;
      revealEl.focus({ preventScroll: true });
    }
  });

  const activeSubslide = useMemo(() => {
    if (!activeCell) {
      return null;
    }
    const target = cellToTarget.get(activeCell.id);
    if (!target) {
      return null;
    }
    return { h: target.h, v: target.v };
  }, [activeCell, cellToTarget]);

  // Forward the deck's current cell to the parent, except while a parked
  // preview is parked: every reveal.js event during that window is an echo
  // of the programmatic park (possibly with transient indices), so ignoring
  // them keeps `activeCellId` pinned on the minimap cell.
  const reportCurrentCell = useEvent(() => {
    if (parkedPreviewCell != null) {
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

  // While parked on a preview, step through minimap order instead of
  // letting reveal.js advance from the parked slide the user can't see.
  const handleParkedNavKey = useEvent((event: KeyboardEvent) => {
    if (!parkedPreviewCell || activeIndex == null) {
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
    if (nextIndex < 0 || nextIndex >= slideCells.length) {
      return;
    }
    onSlideChange?.(nextIndex);
  });

  const handleSlideChange = useEvent(() => {
    reportCurrentCell();
    triggerResize(deckRef.current);
  });

  useEventListener(document, "keydown", handleParkedNavKey, { capture: true });

  const parkedPreviewLabel = isNoOutputPreview
    ? "Hidden as there is no output"
    : "Skipped in presentation";

  const slideArea = (
    <div
      ref={containerRef}
      className="h-full w-full min-w-0 flex items-center justify-center overflow-hidden"
    >
      <div className="group relative" style={{ width, height }}>
        <Deck
          deckRef={deckRef}
          className="aspect-video w-full overflow-hidden border rounded bg-background mo-slides-theme prose-slides focus:outline-none focus-visible:outline-none"
          config={revealConfig}
          onReady={handleDeckReady}
          onSlideChange={handleSlideChange}
          onFragmentShown={reportCurrentCell}
          onFragmentHidden={reportCurrentCell}
          plugins={deckPlugins}
        >
          {composition.stacks.map((stack, h) => {
            if (stack.subslides.length === 1) {
              const isActive =
                activeSubslide?.h === h && activeSubslide?.v === 0;
              return (
                <SubslideView
                  key={h}
                  subslide={stack.subslides[0]}
                  showCode={codeShown && isActive}
                  isEditable={isEditable}
                  slideConfigs={layout.cells}
                />
              );
            }
            return (
              <Stack key={h}>
                {stack.subslides.map((sub, v) => {
                  const isActive =
                    activeSubslide?.h === h && activeSubslide?.v === v;
                  return (
                    <SubslideView
                      key={v}
                      subslide={sub}
                      showCode={codeShown && isActive}
                      isEditable={isEditable}
                      slideConfigs={layout.cells}
                    />
                  );
                })}
              </Stack>
            );
          })}
        </Deck>
        {parkedPreviewCell && (
          <div
            key={parkedPreviewCell.id}
            className="absolute inset-0 z-10 border rounded bg-background flex flex-col overflow-hidden"
            aria-label={parkedPreviewLabel}
          >
            <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/40">
              <EyeOffIcon className="h-3.5 w-3.5" />
              <span>{parkedPreviewLabel}</span>
            </div>
            <div className="flex-1 overflow-auto flex">
              <div
                className={
                  isNoOutputPreview && (isEditable || codeShown)
                    ? "mo-slide-content flex flex-col gap-3"
                    : "mo-slide-content"
                }
                style={{ margin: "auto 20px" }}
              >
                <ParkedPreviewContent
                  cell={parkedPreviewCell}
                  isNoOutputPreview={isNoOutputPreview}
                  isEditable={isEditable}
                  codeShown={codeShown}
                />
              </div>
            </div>
          </div>
        )}
        <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-70 text-muted-foreground transition-opacity">
          {codeToggleEnabled && (
            <Tooltip content={codeShown ? "Hide code (C)" : "Show code (C)"}>
              <Button
                data-testid="marimo-plugin-slides-toggle-code"
                variant="ghost"
                size="icon"
                className={cn(
                  "text-muted-foreground h-7 w-7",
                  codeShown && "text-foreground bg-muted",
                )}
                aria-pressed={codeShown}
                aria-label={codeShown ? "Hide code" : "Show code"}
                onClick={toggleShowCode}
              >
                <CodeIcon className="h-4 w-4" />
              </Button>
            </Tooltip>
          )}
          <Tooltip content="Fullscreen (F)">
            <Button
              data-testid="marimo-plugin-slides-fullscreen"
              variant="ghost"
              size="icon"
              className="text-muted-foreground h-7 w-7"
              aria-label="Enter fullscreen"
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
    </div>
  );

  if (mode === "read") {
    return (
      <div className="flex-1 min-w-0 flex flex-row gap-3">{slideArea}</div>
    );
  }

  return (
    <div className="flex-1 min-w-0 flex flex-row gap-3">
      <PanelGroup
        direction="vertical"
        autoSaveId="marimo:slides:notes-panel"
        className="flex-1 min-w-0"
      >
        <Panel defaultSize={92} minSize={60}>
          {slideArea}
        </Panel>
        <PanelResizeHandle
          className="mo-slides-notes-resize"
          hitAreaMargins={{ coarse: 12, fine: 4 }}
          disabled={isFullscreen}
        />
        <Panel
          defaultSize={10}
          minSize={4}
          collapsible={true}
          collapsedSize={4}
        >
          <SlideNotesEditor
            layout={layout}
            setLayout={setLayout}
            cellId={activeConfigCell?.id}
          />
        </Panel>
      </PanelGroup>
      <SlideSidebar
        configWidth={configWidth}
        layout={layout}
        setLayout={setLayout}
        activeConfigCell={activeConfigCell}
      />
    </div>
  );
};

export default RevealSlidesComponent;
