/* Copyright 2026 Marimo. All rights reserved. */

import {
  type CSSProperties,
  type ReactNode,
  memo,
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
import { outputIsStale } from "@/core/cells/cell";
import type { CellId } from "@/core/cells/ids";
import type { RuntimeCell } from "@/core/cells/types";
import type { RevealApi, RevealConfig } from "reveal.js";
import { useEventListener } from "@/hooks/useEventListener";
import { Events } from "@/utils/events";
import { Functions } from "@/utils/functions";
import { Logger } from "@/utils/Logger";
import "./slides.css";
import "./reveal-slides.css";
import { hasRenderableOutput } from "../editor/renderers/slides-layout/compute-slide-cells";
import type {
  DeckVerticalAlign,
  SlideConfig,
  SlidesLayout,
  SlideType,
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
  DEFAULT_DECK_VERTICAL_ALIGN,
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
import { hasQueryParam, KnownQueryParams } from "@/core/constants";
import { isIslands } from "@/core/islands/utils";
import { useNotebookCodeAvailable } from "@/core/meta/code-visibility";
import { type AppMode, kioskModeAtom } from "@/core/mode";
import { useAtomValue } from "jotai";
import RevealNotes from "reveal.js/plugin/notes";

const ASPECT_RATIO = 16 / 9;
/** Fixed slide size for print/PDF — avoid ResizeObserver racing reveal's print layout. */
const PRINT_WIDTH = 1280;
const PRINT_HEIGHT = 720;

declare global {
  interface Window {
    /** Set when reveal.js finishes print/PDF layout (Playwright wait target). */
    __MARIMO_SLIDES_PDF_READY__?: boolean;
  }
}

const isPrintPdfMode = hasQueryParam(KnownQueryParams.printPdf);

/**
 * Skip all React updates after the initial mount.
 *
 * `@revealjs/react` calls `deck.sync()` on every render when the slide
 * fingerprint changes. Reveal's print view rewrites that DOM, so any
 * re-render during/after print activation can prevent `pdf-ready` from
 * ever firing.
 */
const FreezeAfterMount = memo(
  function FreezeAfterMount({ children }: { children: ReactNode }) {
    return children;
  },
  () => true,
);

/**
 * After outputs look complete, wait this long for late WS messages before
 * freezing the deck tree for print.
 */
const PRINT_DECK_SETTLE_MS = 500;
/** Don't block PDF export forever if some cell never receives an output. */
const PRINT_DECK_MAX_WAIT_MS = 15_000;
/** After unhiding print pages, wait for widgets to paint before pruning empties. */
const PRINT_CONTENT_PAINT_MS = 800;

function printPageHasContent(page: Element): boolean {
  const text = (page.textContent || "").replace(/\s+/g, " ").trim();
  if (text.length > 0) {
    return true;
  }
  return (
    page.querySelector(
      "img, svg, canvas, table, video, iframe, .vega-embed, .marimo-table",
    ) != null
  );
}

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

/**
 * Resolve whether a slide cell shows its source instead of its output.
 *
 * Code is shown when either the cell's persisted `showCode` config is set or
 * the keyboard toggle `C` override is active for it (logical OR).
 */
export function shouldShowCode(options: {
  cells: ReadonlyMap<CellId, SlideConfig>;
  cellId: CellId | undefined;
  showCodeOverrides: ReadonlySet<CellId>;
  codeToggleEnabled: boolean;
}): boolean {
  const { cells, cellId, showCodeOverrides, codeToggleEnabled } = options;
  if (cellId == null || !codeToggleEnabled) {
    return false;
  }
  const configured = cells.get(cellId)?.showCode ?? false;
  return configured || showCodeOverrides.has(cellId);
}

/**
 * The slide type a cell takes *in the composed deck*. Cells without output and
 * the cell currently held in the parked edit overlay are dropped (`"skip"`) so
 * they aren't mounted a second time in the deck — the overlay renders them
 * instead. Everything else uses its configured type, defaulting to a slide.
 */
export function deckSlideType(options: {
  cell: RuntimeCell;
  noOutputIds: ReadonlySet<CellId>;
  heldEditCellId: CellId | null;
  slideConfigs: ReadonlyMap<CellId, SlideConfig>;
}): SlideType {
  const { cell, noOutputIds, heldEditCellId, slideConfigs } = options;
  if (noOutputIds.has(cell.id) || cell.id === heldEditCellId) {
    return "skip";
  }
  return slideConfigs.get(cell.id)?.type ?? DEFAULT_SLIDE_TYPE;
}

/**
 * Tracks the cell pinned in the parked overlay (rendered over the deck for
 * skipped / output-less cells, and during in-progress edits).
 *
 * A brand-new (or output-less) cell is edited in the parked overlay, which
 * lives outside reveal's slide DOM. The moment it first produces output it
 * would normally jump to its composed slide — a different React subtree that
 * reveal also re-syncs/transitions — tearing down the editor and dropping
 * focus mid-edit (e.g. typing in a new markdown cell). To avoid that we *hold*
 * the cell in the overlay even after it gains output, and only let it settle
 * into the deck once the user navigates to a different cell.
 *
 * The hold is keyed off the active cell rather than DOM focus on purpose: the
 * slide editor doesn't participate in the global cell-focus state, and the
 * active cell only changes when the user moves in the minimap — exactly when
 * we want to release the hold.
 *
 * Returns:
 * - `parkedPreviewCell`: the cell to render in the overlay
 * - `isHeldEdit`: whether the cell is held in the overlay
 * - `isNoOutputPreview`: whether the cell is output-less
 * - `heldEditCellId`: the id of the cell that is held in the overlay
 */
export function useParkedPreview(options: {
  activeCell: RuntimeCell | undefined;
  slideConfigs: ReadonlyMap<CellId, SlideConfig>;
  noOutputIds: ReadonlySet<CellId>;
}): {
  parkedPreviewCell: RuntimeCell | null;
  isHeldEdit: boolean;
  isNoOutputPreview: boolean;
  heldEditCellId: CellId | null;
  heldShowsCode: boolean;
  toggleHeldShowsCode: () => void;
} {
  const { activeCell, slideConfigs, noOutputIds } = options;
  const activeCellId = activeCell?.id ?? null;
  const isNoOutputPreview =
    activeCell != null && noOutputIds.has(activeCell.id);
  const isSkippedPreview =
    activeCell != null && slideConfigs.get(activeCell.id)?.type === "skip";
  // Genuinely parked: skipped in the deck, or no output to compose yet.
  const baseParked = isSkippedPreview || isNoOutputPreview;

  // The cell pinned in the overlay, tracked alongside the active cell it was
  // armed against so we can release it exactly when the active cell changes.
  const [held, setHeld] = useState<{
    activeCellId: CellId | null;
    cellId: CellId | null;
  }>({ activeCellId, cellId: null });

  let heldCellId = held.cellId;
  if (held.activeCellId !== activeCellId) {
    // Active cell changed: drop any prior hold, arming a fresh one only while
    // the new cell has no output yet (skipped cells park via `baseParked`).
    heldCellId = isNoOutputPreview ? activeCellId : null;
    setHeld({ activeCellId, cellId: heldCellId });
  } else if (isNoOutputPreview && heldCellId !== activeCellId) {
    // Same active cell, still output-less: (re)arm the hold.
    heldCellId = activeCellId;
    setHeld({ activeCellId, cellId: heldCellId });
  }

  const isHeldEdit =
    !baseParked && activeCellId != null && heldCellId === activeCellId;
  // Keep the held cell out of the composed deck so its editor isn't mounted a
  // second time (the overlay already renders it); it rejoins once released.
  const heldEditCellId = isHeldEdit ? heldCellId : null;

  // Code visibility for the held overlay. Defaults to showing the editor so it
  // survives the no-output -> output transition mid-edit; the `C` toggle can
  // hide it on demand.
  const [heldShow, setHeldShow] = useState<{
    cellId: CellId | null;
    show: boolean;
  }>({ cellId: heldEditCellId, show: true });
  let heldShowsCode = heldShow.show;
  if (heldShow.cellId !== heldEditCellId) {
    heldShowsCode = true;
    setHeldShow({ cellId: heldEditCellId, show: true });
  }
  const toggleHeldShowsCode = useEvent(() =>
    setHeldShow((prev) => ({ ...prev, show: !prev.show })),
  );

  return {
    parkedPreviewCell: baseParked || isHeldEdit ? (activeCell ?? null) : null,
    isHeldEdit,
    isNoOutputPreview,
    heldEditCellId,
    heldShowsCode,
    toggleHeldShowsCode,
  };
}

/**
 * Margin style that positions a slide's content vertically within the
 * full-height slide. The content is a flex item, so the vertical margins decide
 * where the free space lands: `auto` on both sides centers it, while pinning one
 * side to `0` pushes content to the top or bottom. The horizontal `20px` keeps
 * content off the slide edges regardless of alignment.
 */
function resolveSlideContentStyle(
  verticalAlign: DeckVerticalAlign | undefined,
): CSSProperties {
  switch (verticalAlign ?? DEFAULT_DECK_VERTICAL_ALIGN) {
    case "top":
      return { margin: "0 20px auto" };
    case "bottom":
      return { margin: "auto 20px 0" };
    default:
      return { margin: "auto 20px" };
  }
}

const SubslideView = ({
  subslide,
  resolveShowCode,
  isEditable,
  slideConfigs,
  contentStyle,
  /**
   * Print/PDF: render fragment blocks inline (no `.fragment` wrapper) so
   * reveal's print layout measures full content height and nothing stays at
   * `opacity: 0` / gets clipped.
   */
  flattenFragments = false,
}: {
  subslide: ComposedSubslide<RuntimeCell>;
  resolveShowCode: (cellId: CellId) => boolean;
  isEditable: boolean;
  slideConfigs: ReadonlyMap<CellId, SlideConfig>;
  contentStyle: CSSProperties;
  flattenFragments?: boolean;
}) => {
  const { slideLevel, cumulativeByBlock } = buildSubslideNotes(
    subslide,
    slideConfigs,
  );

  const anyCodeShown = subslide.blocks.some((block) =>
    block.cells.some((cell) => resolveShowCode(cell.id)),
  );

  return (
    <Slide>
      <div
        className={cn(
          "h-full w-full flex",
          isPrintPdfMode ? "overflow-hidden" : "overflow-auto",
        )}
      >
        <div
          className={
            anyCodeShown
              ? "mo-slide-content flex flex-col gap-3"
              : "mo-slide-content"
          }
          style={contentStyle}
        >
          {subslide.blocks.map((block, i) => {
            const rendered = block.cells.map((cell) => {
              if (!resolveShowCode(cell.id)) {
                return (
                  <CellOutputSlide
                    key={cell.id}
                    cellId={cell.id}
                    status={cell.status}
                    output={cell.output}
                    stale={outputIsStale(cell, false)}
                  />
                );
              }
              return isEditable ? (
                <SlideCellView key={cell.id} cell={cell} />
              ) : (
                <SlideCellReadOnlyView key={cell.id} cell={cell} />
              );
            });
            if (block.isFragment && !flattenFragments) {
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

/**
 * Whether the parked overlay renders the cell's *source* instead of its output.
 */
export function parkedRendersSource(options: {
  isNoOutputPreview: boolean;
  isEditable: boolean;
  showCode: boolean;
}): boolean {
  const { isNoOutputPreview, isEditable, showCode } = options;
  return isNoOutputPreview ? isEditable || showCode : showCode;
}

const ParkedPreviewContent = ({
  cell,
  isNoOutputPreview,
  isEditable,
  showCode,
}: {
  cell: RuntimeCell;
  isNoOutputPreview: boolean;
  isEditable: boolean;
  showCode: boolean;
}) => {
  if (parkedRendersSource({ isNoOutputPreview, isEditable, showCode })) {
    // Editable cells get the live editor; otherwise a read-only source view.
    return isEditable ? (
      <SlideCellView cell={cell} />
    ) : (
      <SlideCellReadOnlyView cell={cell} />
    );
  }
  return (
    <CellOutputSlide
      cellId={cell.id}
      status={cell.status}
      output={cell.output}
      stale={outputIsStale(cell, false)}
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
  const liveDims = useSlideDimensions(containerRef);
  const width = isPrintPdfMode ? PRINT_WIDTH : liveDims.width;
  const height = isPrintPdfMode ? PRINT_HEIGHT : liveDims.height;
  const isFullscreen = useFullScreenElement() != null;
  // In print mode, delay mounting the Deck until cells exist and outputs have
  // had a chance to replay — then freeze the tree so sync() cannot race print.
  const [printDeckGateOpen, setPrintDeckGateOpen] = useState(false);
  const [printGateTick, setPrintGateTick] = useState(0);
  const printGateStartedAtRef = useRef<number | null>(null);
  const printRenderableCountRef = useRef(-1);
  const printStableSinceRef = useRef<number | null>(null);
  const printFinalizeStartedRef = useRef(false);

  // Skip the Notes plugin inside reveal's own speaker-view iframes so pressing
  // `S` there doesn't try to spawn another popup.
  const kioskMode = useAtomValue(kioskModeAtom);
  const deckPlugins = useMemo(
    () => (kioskMode || isPrintPdfMode ? [] : [RevealNotes]),
    [kioskMode],
  );

  // Mount the print deck once non-skip outputs look stable. Cells that never
  // produce output are omitted from the composed deck (via deckSlideType), so
  // we only wait for a stable renderable count — not "every cell forever".
  useEffect(() => {
    if (!isPrintPdfMode || printDeckGateOpen) {
      return;
    }
    if (slideCells.length === 0) {
      return;
    }
    if (printGateStartedAtRef.current == null) {
      printGateStartedAtRef.current = Date.now();
    }

    const busy = slideCells.some(
      (cell) => cell.status === "running" || cell.status === "queued",
    );
    const renderableCount = slideCells.filter((cell) => {
      const type = layout.cells.get(cell.id)?.type ?? DEFAULT_SLIDE_TYPE;
      return type !== "skip" && hasRenderableOutput(cell);
    }).length;

    if (renderableCount !== printRenderableCountRef.current) {
      printRenderableCountRef.current = renderableCount;
      printStableSinceRef.current = Date.now();
    }

    const elapsed = Date.now() - (printGateStartedAtRef.current ?? Date.now());
    const timedOut = elapsed >= PRINT_DECK_MAX_WAIT_MS;
    const stableFor =
      printStableSinceRef.current == null
        ? 0
        : Date.now() - printStableSinceRef.current;
    const outputsStable =
      renderableCount > 0 && stableFor >= PRINT_DECK_SETTLE_MS;

    if (timedOut || (!busy && outputsStable)) {
      if (timedOut) {
        Logger.warn(
          "Slides PDF: opening print deck after max wait with incomplete outputs",
          { renderableCount, busy },
        );
      }
      setPrintDeckGateOpen(true);
      return;
    }

    const waitMs = Math.min(
      busy ? 250 : Math.max(PRINT_DECK_SETTLE_MS - stableFor, 50),
      Math.max(PRINT_DECK_MAX_WAIT_MS - elapsed, 50),
    );
    const timer = window.setTimeout(() => {
      setPrintGateTick((tick) => tick + 1);
    }, waitMs);
    return () => window.clearTimeout(timer);
  }, [slideCells, layout.cells, printDeckGateOpen, printGateTick]);

  // Store the state of the code toggle for each cell
  // This acts like a 'peek' at the code.
  const [showCodeOverrides, setShowCodeOverrides] = useState<
    ReadonlySet<CellId>
  >(() => new Set());
  const codeAvailable = useNotebookCodeAvailable(slideCells);
  const codeToggleEnabled = !isIslands() && codeAvailable;

  const activeCell = activeIndex != null ? slideCells[activeIndex] : undefined;
  // Fall back to the first cell while the deck settles on an initial slide.
  // Still `undefined` when the deck is empty (handled below).
  const activeConfigCell = activeCell ?? slideCells.at(0);

  const {
    parkedPreviewCell,
    isHeldEdit,
    isNoOutputPreview,
    heldEditCellId,
    heldShowsCode,
    toggleHeldShowsCode,
  } = useParkedPreview({
    activeCell,
    slideConfigs: layout.cells,
    noOutputIds,
  });

  const resolveShowCode = (cellId: CellId | undefined): boolean =>
    shouldShowCode({
      cells: layout.cells,
      cellId,
      showCodeOverrides,
      codeToggleEnabled,
    });

  // `C` and the toolbar button target the active slide's cell (the revealed
  // fragment when stepping through a stack, otherwise the lead cell).
  const cellIdToShowCode = activeCell?.id ?? activeConfigCell?.id;
  const cellShowsCode = isHeldEdit
    ? heldShowsCode
    : resolveShowCode(cellIdToShowCode);

  // A slide persisted with `showCode: true` always renders code
  const codeAlwaysShown =
    codeToggleEnabled &&
    cellIdToShowCode != null &&
    (layout.cells.get(cellIdToShowCode)?.showCode ?? false);

  const composition = useMemo(
    () =>
      composeSlides({
        cells: slideCells,
        getType: (cell) =>
          deckSlideType({
            cell,
            noOutputIds,
            heldEditCellId,
            slideConfigs: layout.cells,
          }),
      }),
    [slideCells, noOutputIds, layout.cells, heldEditCellId],
  );

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
  const slideContentStyle = resolveSlideContentStyle(
    layout.deck?.verticalAlign,
  );

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
      // Print view needs a non-embedded deck so reveal can linearize slides
      // into `.pdf-page` wrappers for Chromium's print pipeline.
      embedded: !isPrintPdfMode,
      width,
      height,
      // Print: center the slide box on each PDF page (reveal only sets width
      // on sections; our CSS forces full slide height for content layout).
      center: isPrintPdfMode,
      minScale: 0.2,
      maxScale: 2,
      margin: isPrintPdfMode ? 0 : 0.04,
      transition: isPrintPdfMode ? "none" : deckTransition,
      keyboardCondition: (event: KeyboardEvent) => !Events.fromInput(event),
      url: kioskUrl,
      // reveal.js auto-switches to its scroll view for mobile.
      // We disable this mode because it rewrites the slide DOM that
      // `@revealjs/react` owns, which crashes on `reveal.sync()` re-renders.
      scrollActivationWidth: 0,
      ...(isPrintPdfMode && {
        view: "print" as const,
        // Print deck is flattened (no stacks / fragment wrappers), so each
        // composed subslide is already one horizontal section / PDF page.
        pdfSeparateFragments: false,
        // A slightly-tall slide must not split into a content page + blank
        // overflow page in Chromium's PDF pipeline.
        pdfMaxPagesPerSlide: 1,
      }),
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
    if (isPrintPdfMode) {
      return;
    }
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
    if (cellIdToShowCode == null || codeAlwaysShown) {
      return;
    }
    if (isHeldEdit) {
      toggleHeldShowsCode();
      return;
    }
    startTransition(() =>
      setShowCodeOverrides((prev) => {
        const next = new Set(prev);
        if (next.has(cellIdToShowCode)) {
          next.delete(cellIdToShowCode);
        } else {
          next.add(cellIdToShowCode);
        }
        return next;
      }),
    );
  });

  const markPdfReady = useEvent(() => {
    if (window.__MARIMO_SLIDES_PDF_READY__ || printFinalizeStartedRef.current) {
      return;
    }
    if (document.querySelector(".pdf-page") == null) {
      return;
    }
    printFinalizeStartedRef.current = true;

    const unhidePrintSections = () => {
      // Reveal marks inactive slides with the `hidden` attribute for a11y.
      // Print view moves those nodes under `.pdf-page` but leaves `hidden` set,
      // and Tailwind preflight's `[hidden] { display: none !important }` then
      // blanks every page after the initially-present slide in the PDF.
      document.querySelectorAll(".pdf-page > section").forEach((section) => {
        section.removeAttribute("hidden");
        if (section instanceof HTMLElement) {
          section.style.setProperty("display", "block", "important");
        }
      });
    };

    const finalize = () => {
      unhidePrintSections();
      // Print surfaces are white; drop dark-mode so inverted prose isn't
      // white-on-white (Agenda / Thanks look blank otherwise).
      document.documentElement.classList.remove("dark");
      document.documentElement.style.colorScheme = "light";
      // Drop pages that never received visible content (failed UI widgets,
      // output-less cells that still opened a subslide, etc.). Page sizing and
      // one-sheet-per-wrapper are enforced by reveal-slides.css.
      for (const page of document.querySelectorAll(".pdf-page")) {
        if (!printPageHasContent(page)) {
          page.remove();
        }
      }
      const pageCount = document.querySelectorAll(".pdf-page").length;
      document.documentElement.classList.add("marimo-slides-pdf-ready");
      window.__MARIMO_SLIDES_PDF_READY__ = true;
      Logger.log("Slides PDF: reveal print layout ready", { pageCount });
    };

    unhidePrintSections();
    window.setTimeout(finalize, PRINT_CONTENT_PAINT_MS);
  });

  const handleDeckReady = useEvent((deck: RevealApi) => {
    if (!isPrintPdfMode) {
      navigateDeckToActiveCell(deck);
      if (codeToggleEnabled) {
        deck.addKeyBinding(
          {
            keyCode: 67,
            key: "C",
            description: "Toggle code editor",
          },
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
      return;
    }

    // `@revealjs/react` calls `deck.sync()` / `syncSlide()` from a layout
    // effect right after `initialize()` resolves. That undoes print view's
    // `.pdf-page` rewrite and leaves only the present slide visible — so we
    // no-op those APIs for the life of this print deck.
    deck.sync = Functions.NOOP;
    const deckWithSlideSync = deck as RevealApi & {
      syncSlide?: (slide?: HTMLElement) => void;
    };
    if (typeof deckWithSlideSync.syncSlide === "function") {
      deckWithSlideSync.syncSlide = Functions.NOOP;
    }

    // Print view fires `pdf-ready` during initialize (before this handler).
    // Wait a frame so the React layout-effect sync no-op has run, then confirm
    // pages are still in the DOM before unblocking Playwright.
    deck.on("pdf-ready", markPdfReady);
    requestAnimationFrame(() => {
      if (document.querySelector(".pdf-page") != null) {
        markPdfReady();
      }
    });
  });

  // Backup poller: if pdf-ready was missed, still unblock Playwright once
  // reveal has created `.pdf-page` wrappers (class `print-pdf` alone is too
  // early — reveal adds it before pages are built).
  useEffect(() => {
    if (!isPrintPdfMode || !printDeckGateOpen) {
      return;
    }
    const timer = window.setInterval(() => {
      if (document.querySelectorAll(".pdf-page").length > 0) {
        markPdfReady();
        window.clearInterval(timer);
      }
    }, 100);
    return () => window.clearInterval(timer);
  }, [printDeckGateOpen, markPdfReady]);

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
  });

  useEventListener(document, "keydown", handleParkedNavKey, { capture: true });

  // `isHeldEdit` means the cell already produces output and is only kept in the
  // overlay so the editor survives the edit, so the parked banners don't apply.
  const parkedPreviewLabel = isHeldEdit
    ? null
    : isNoOutputPreview
      ? "Hidden as there is no output"
      : "Skipped in presentation";

  const parkedShowCode = isHeldEdit
    ? heldShowsCode
    : resolveShowCode(parkedPreviewCell?.id);
  const parkedShowsSource = parkedRendersSource({
    isNoOutputPreview,
    isEditable,
    showCode: parkedShowCode,
  });

  const deckTree = (
    <Deck
      deckRef={deckRef}
      className={cn(
        "w-full bg-background mo-slides-theme prose-slides focus:outline-hidden focus-visible:outline-hidden",
        isPrintPdfMode
          ? "border-0 rounded-none"
          : "aspect-video overflow-hidden border rounded",
      )}
      config={revealConfig}
      onReady={handleDeckReady}
      onSlideChange={handleSlideChange}
      onFragmentShown={reportCurrentCell}
      onFragmentHidden={reportCurrentCell}
      plugins={deckPlugins}
    >
      {isPrintPdfMode
        ? // Flatten stacks + fragments into top-level slides. Reveal's print
          // view skips `section.stack` wrappers and measures height while
          // `.fragment` nodes are still hidden — both of which drop nested /
          // fragment content from the PDF. Omit subslides with no renderable
          // output so we don't emit blank PDF pages.
          composition.stacks.flatMap((stack, h) =>
            stack.subslides
              .filter((sub) =>
                sub.blocks.some((block) =>
                  block.cells.some((cell) => hasRenderableOutput(cell)),
                ),
              )
              .map((sub, v) => (
                <SubslideView
                  key={`${h}-${v}`}
                  subslide={sub}
                  resolveShowCode={resolveShowCode}
                  isEditable={false}
                  slideConfigs={layout.cells}
                  contentStyle={slideContentStyle}
                  flattenFragments={true}
                />
              )),
          )
        : composition.stacks.map((stack, h) => {
            if (stack.subslides.length === 1) {
              return (
                <SubslideView
                  key={h}
                  subslide={stack.subslides[0]}
                  resolveShowCode={resolveShowCode}
                  isEditable={isEditable}
                  slideConfigs={layout.cells}
                  contentStyle={slideContentStyle}
                />
              );
            }
            return (
              <Stack key={h}>
                {stack.subslides.map((sub, v) => {
                  return (
                    <SubslideView
                      key={v}
                      subslide={sub}
                      resolveShowCode={resolveShowCode}
                      isEditable={isEditable}
                      slideConfigs={layout.cells}
                      contentStyle={slideContentStyle}
                    />
                  );
                })}
              </Stack>
            );
          })}
    </Deck>
  );

  const shouldRenderDeck = !isPrintPdfMode || printDeckGateOpen;

  const slideArea = (
    <div
      ref={containerRef}
      className={
        isPrintPdfMode
          ? "w-full min-w-0"
          : "h-full w-full min-w-0 flex items-center justify-center overflow-hidden"
      }
    >
      <div
        className={cn("group relative", !isPrintPdfMode && "h-full")}
        style={isPrintPdfMode ? undefined : { width, height }}
      >
        {shouldRenderDeck &&
          (isPrintPdfMode ? (
            <FreezeAfterMount>{deckTree}</FreezeAfterMount>
          ) : (
            deckTree
          ))}
        {!isPrintPdfMode && parkedPreviewCell && (
          <div
            key={parkedPreviewCell.id}
            className="absolute inset-0 z-10 border rounded bg-background flex flex-col overflow-hidden"
            aria-label={parkedPreviewLabel ?? undefined}
          >
            {parkedPreviewLabel && (
              <div className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground border-b bg-muted/40">
                <EyeOffIcon className="h-3.5 w-3.5" />
                <span>{parkedPreviewLabel}</span>
              </div>
            )}
            <div className="flex-1 overflow-auto flex">
              <div
                className={
                  parkedShowsSource
                    ? "mo-slide-content flex flex-col gap-3"
                    : "mo-slide-content"
                }
                style={slideContentStyle}
              >
                <ParkedPreviewContent
                  cell={parkedPreviewCell}
                  isNoOutputPreview={isNoOutputPreview}
                  isEditable={isEditable}
                  showCode={parkedShowCode}
                />
              </div>
            </div>
          </div>
        )}
        {!isPrintPdfMode && (
          <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-70 text-muted-foreground transition-opacity">
            {codeToggleEnabled && (
              <Tooltip
                content={
                  codeAlwaysShown
                    ? "Code is always shown for this slide"
                    : cellShowsCode
                      ? "Hide code (C)"
                      : "Show code (C)"
                }
              >
                <Button
                  data-testid="marimo-plugin-slides-toggle-code"
                  variant="ghost"
                  size="icon"
                  // Stay hoverable (no `disabled` attr) so the tooltip can
                  // explain why the toggle is inert when code is pinned on.
                  className={cn(
                    "text-muted-foreground h-7 w-7",
                    cellShowsCode && "text-foreground bg-muted",
                    codeAlwaysShown && "opacity-50 cursor-not-allowed",
                  )}
                  aria-pressed={cellShowsCode}
                  aria-disabled={codeAlwaysShown}
                  aria-label={
                    codeAlwaysShown
                      ? "Code always shown"
                      : cellShowsCode
                        ? "Hide code"
                        : "Show code"
                  }
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
        )}
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
