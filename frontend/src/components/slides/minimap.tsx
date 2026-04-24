/* Copyright 2026 Marimo. All rights reserved. */

import { useCellActions, useCellIds } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import type { CellColumnId } from "@/utils/id-tree";
import { useEffect, useRef, useState } from "react";
import type { ICellRendererProps } from "../editor/renderers/types";
import type {
  SlideType,
  SlidesLayout,
} from "../editor/renderers/slides-layout/types";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  type DragMoveEvent,
  type DragOverEvent,
  type DragStartEvent,
  type DragEndEvent,
  closestCenter,
  pointerWithin,
  type CollisionDetection,
  type UniqueIdentifier,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { restrictToVerticalAxis } from "@dnd-kit/modifiers";
import { cn } from "@/utils/cn";
import { Slide } from "./slide";
import { InfoIcon, type LucideIcon } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { Logger } from "@/utils/Logger";
import { SLIDE_TYPE_OPTIONS_BY_VALUE } from "./slide-form";

type Props = ICellRendererProps<SlidesLayout>;
type SlideCell = Props["cells"][number];
type CellIdsState = ReturnType<typeof useCellIds>;
type DropPosition = "before" | "after";

interface ProjectedDropTarget {
  overId: CellId;
  position: DropPosition;
}

interface ResolvedDropTarget {
  cellId: CellId;
  columnId: CellColumnId;
  index: number;
}

interface ThumbnailDimensions {
  width: number;
  height: number;
  scale: number;
}

interface SlideThumbnailCardProps extends React.HTMLAttributes<HTMLDivElement> {
  cell: SlideCell;
  dimensions: ThumbnailDimensions;
  isActiveSlide?: boolean;
  isActiveDragSource?: boolean;
  isOverlay?: boolean;
  isVisible?: boolean;
  slideType?: SlideType;
  ref?: React.Ref<HTMLDivElement>;
}

interface SlideThumbnailRowProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  cell: SlideCell;
  dimensions: ThumbnailDimensions;
  isActiveSlide?: boolean;
  dropIndicator?: DropPosition | null;
  isActiveDragSource?: boolean;
  isVisible?: boolean;
  slideType?: SlideType;
  ref?: React.Ref<HTMLButtonElement>;
}

interface SlidesMinimapProps {
  cells: SlideCell[];
  thumbnailWidth: number;
  canReorder: boolean;
  activeCellId: CellId | null;
  // Set of cell ids that are marked `skip` in the slides layout.
  skippedIds?: ReadonlySet<CellId>;
  slideTypes?: ReadonlyMap<CellId, SlideType>;
  onSlideClick: (index: number) => void;
}

function getSlideTypeVisual(
  slideType: SlideType | undefined,
): { label: string; description: string; Icon: LucideIcon } | null {
  if (!slideType || slideType === "slide") {
    return null;
  }
  const { label, description, Icon } = SLIDE_TYPE_OPTIONS_BY_VALUE[slideType];
  return { label, description, Icon };
}

const SLIDE_ASPECT_RATIO = 16 / 9;
const SLIDE_BASE_WIDTH = 960;

function computeThumbnailDimensions(width: number): ThumbnailDimensions {
  return {
    width,
    height: width / SLIDE_ASPECT_RATIO,
    scale: width / SLIDE_BASE_WIDTH,
  };
}
const MINIMAP_AUTO_SCROLL = {
  threshold: { x: 0, y: 0.1 },
};
const MINIMAP_GAP = 8;
const VISIBILITY_ROOT_MARGIN = "200px 0px";
const minimapCollisionDetection: CollisionDetection = (args) => {
  const pointerCollisions = pointerWithin(args);
  return pointerCollisions.length > 0 ? pointerCollisions : closestCenter(args);
};

/**
 * Tracks which `[data-cell-id]` elements inside a scrollable container are
 * within (or near) the viewport using a single shared IntersectionObserver.
 * A MutationObserver re-observes when children are added or removed.
 * Off-screen thumbnails can skip rendering expensive <Slide> content.
 */
function useVisibleCellIds(
  containerRef: React.RefObject<HTMLDivElement | null>,
): ReadonlySet<CellId> {
  const [visibleIds, setVisibleIds] = useState<ReadonlySet<CellId>>(
    () => new Set(),
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        setVisibleIds((prev) => {
          const next = new Set(prev);
          let changed = false;
          for (const entry of entries) {
            const id = (entry.target as HTMLElement).dataset.cellId as
              | CellId
              | undefined;
            if (!id) {
              continue;
            }
            if (entry.isIntersecting && !next.has(id)) {
              next.add(id);
              changed = true;
            } else if (!entry.isIntersecting && next.has(id)) {
              next.delete(id);
              changed = true;
            }
          }
          return changed ? next : prev;
        });
      },
      { root: container, rootMargin: VISIBILITY_ROOT_MARGIN },
    );

    const observeAll = () => {
      intersectionObserver.disconnect();
      for (const el of container.querySelectorAll<HTMLElement>(
        "[data-cell-id]",
      )) {
        intersectionObserver.observe(el);
      }
    };

    observeAll();

    const mutationObserver = new MutationObserver(observeAll);
    mutationObserver.observe(container, { childList: true });

    return () => {
      intersectionObserver.disconnect();
      mutationObserver.disconnect();
    };
  }, [containerRef]);

  return visibleIds;
}

export const SlidesMinimap = ({
  cells,
  thumbnailWidth,
  canReorder,
  activeCellId,
  skippedIds,
  slideTypes,
  onSlideClick,
}: SlidesMinimapProps) => {
  const cellIds = useCellIds();
  const { moveCellToIndex } = useCellActions();
  const containerRef = useRef<HTMLDivElement>(null);
  const visibleIds = useVisibleCellIds(containerRef);
  const [activeId, setActiveId] = useState<CellId | null>(null);
  const [dropTarget, setDropTarget] = useState<ProjectedDropTarget | null>(
    null,
  );
  const dimensions = computeThumbnailDimensions(thumbnailWidth);

  useEffect(() => {
    if (!activeCellId || !containerRef.current) {
      return;
    }
    const el = containerRef.current.querySelector(
      `[data-cell-id="${activeCellId}"]`,
    );
    el?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [activeCellId]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
  );

  const activeCell = activeId
    ? (cells.find((cell) => cell.id === activeId) ?? null)
    : null;

  const resetDragState = () => {
    setActiveId(null);
    setDropTarget(null);
  };

  const updateDropTarget = (event: DragMoveEvent | DragOverEvent) => {
    const next = projectDropTarget(event);

    setDropTarget((prev) => {
      if (prev?.overId === next?.overId && prev?.position === next?.position) {
        return prev;
      }
      return next;
    });
  };

  const handleDragStart = (event: DragStartEvent) => {
    setDropTarget(null);
    const cellId = asCellId(event.active.id);
    if (cellId) {
      setActiveId(cellId);
    }
  };

  const handleDragEnd = (_event: DragEndEvent) => {
    try {
      if (activeId && dropTarget) {
        const resolvedTarget = resolveDropTarget({
          cellIds,
          activeId,
          target: dropTarget,
        });
        if (resolvedTarget) {
          moveCellToIndex(resolvedTarget);
        }
      }
    } catch (e) {
      Logger.warn("Drop failed", e);
    } finally {
      resetDragState();
    }
  };

  if (!canReorder) {
    return (
      <SlideThumbnailsContainer ref={containerRef}>
        <div className="text-xs text-gray-500 flex items-center gap-0.5">
          <InfoIcon className="h-3 w-3" />
          Reordering is not supported in multi-column mode
        </div>
        {cells.map((cell, index) => (
          <SlideThumbnailRow
            key={cell.id}
            cell={cell}
            dimensions={dimensions}
            isActiveSlide={cell.id === activeCellId}
            isVisible={visibleIds.has(cell.id)}
            slideType={resolveSlideType({
              cellId: cell.id,
              slideTypes,
              skippedIds,
            })}
            onClick={() => onSlideClick(index)}
          />
        ))}
      </SlideThumbnailsContainer>
    );
  }

  return (
    <DndContext
      autoScroll={MINIMAP_AUTO_SCROLL}
      collisionDetection={minimapCollisionDetection}
      modifiers={[restrictToVerticalAxis]}
      sensors={sensors}
      onDragStart={handleDragStart}
      onDragMove={updateDropTarget}
      onDragOver={updateDropTarget}
      onDragEnd={handleDragEnd}
      onDragCancel={resetDragState}
    >
      <SlideThumbnailsContainer ref={containerRef}>
        <SortableContext
          items={cells.map((cell) => cell.id)}
          strategy={verticalListSortingStrategy}
        >
          {cells.map((cell, index) => (
            <SortableSlideThumbnail
              key={cell.id}
              cell={cell}
              dimensions={dimensions}
              isActive={activeId === cell.id}
              isActiveSlide={cell.id === activeCellId}
              isVisible={visibleIds.has(cell.id)}
              slideType={resolveSlideType({
                cellId: cell.id,
                slideTypes,
                skippedIds,
              })}
              dropIndicator={
                dropTarget?.overId === cell.id && activeId !== cell.id
                  ? dropTarget.position
                  : null
              }
              onClick={() => onSlideClick(index)}
            />
          ))}
        </SortableContext>
      </SlideThumbnailsContainer>
      <DragOverlay>
        {activeCell && (
          <SlideThumbnailCard
            cell={activeCell}
            dimensions={dimensions}
            isOverlay={true}
            isActiveDragSource={true}
          />
        )}
      </DragOverlay>
    </DndContext>
  );
};

const SlideThumbnailsContainer = ({
  children,
  ref,
}: {
  children: React.ReactNode;
  ref?: React.Ref<HTMLDivElement>;
}) => {
  return (
    <div
      ref={ref}
      className="h-full overflow-auto flex flex-col scrollbar-thin"
    >
      {children}
    </div>
  );
};

interface SortableSlideThumbnailProps {
  cell: SlideCell;
  dimensions: ThumbnailDimensions;
  dropIndicator?: DropPosition | null;
  isActive: boolean;
  isActiveSlide?: boolean;
  isVisible?: boolean;
  slideType?: SlideType;
  onClick?: () => void;
}

const SortableSlideThumbnail = ({
  cell,
  dimensions,
  dropIndicator,
  isActive,
  isActiveSlide,
  isVisible,
  slideType,
  onClick,
}: SortableSlideThumbnailProps) => {
  const { attributes, listeners, setNodeRef } = useSortable({
    id: cell.id,
  });

  return (
    <SlideThumbnailRow
      ref={setNodeRef}
      cell={cell}
      dimensions={dimensions}
      dropIndicator={dropIndicator}
      isActiveDragSource={isActive}
      isActiveSlide={isActiveSlide}
      isVisible={isVisible}
      slideType={slideType}
      onClick={onClick}
      {...attributes}
      {...listeners}
    />
  );
};

const SlideThumbnailRow = ({
  cell,
  dimensions,
  className,
  style,
  dropIndicator,
  isActiveSlide = false,
  isActiveDragSource = false,
  isVisible,
  slideType,
  onClick,
  ref,
  ...props
}: SlideThumbnailRowProps) => {
  const rowStyle: React.CSSProperties = {
    paddingTop: MINIMAP_GAP,
    paddingBottom: MINIMAP_GAP,
    ...style,
  };

  return (
    <button
      ref={ref}
      type="button"
      data-cell-id={cell.id}
      className={cn(
        "relative shrink-0 appearance-none text-left p-0 bg-transparent outline-none",
        className,
      )}
      style={rowStyle}
      onClick={onClick}
      {...props}
    >
      {dropIndicator && (
        <div
          className={cn(
            "absolute left-2 right-2 h-0.5 rounded-full bg-blue-500 z-20 pointer-events-none",
            dropIndicator === "after"
              ? "bottom-0 translate-y-1/2"
              : "top-0 -translate-y-1/2",
          )}
        />
      )}
      <SlideThumbnailCard
        cell={cell}
        dimensions={dimensions}
        isActiveSlide={isActiveSlide}
        isActiveDragSource={isActiveDragSource}
        isVisible={isVisible}
        slideType={slideType}
      />
    </button>
  );
};

const SlideThumbnailCard = ({
  cell,
  dimensions,
  className,
  style,
  isActiveSlide = false,
  isActiveDragSource = false,
  isOverlay = false,
  isVisible = false,
  slideType,
  ref,
  ...props
}: SlideThumbnailCardProps) => {
  const { width, height, scale } = dimensions;
  const visual = getSlideTypeVisual(slideType);
  const isSkipped = slideType === "skip";

  const outerStyle: React.CSSProperties = {
    width,
    height,
    contain: "strict",
    ...(isOverlay
      ? null
      : {
          contentVisibility: "auto",
          containIntrinsicSize: `${width}px ${height}px`,
        }),
    ...style,
  };

  const showContent = isVisible || isOverlay;

  return (
    <div
      ref={ref}
      className={cn(
        "border-2 shrink-0 rounded-md relative select-none bg-background cursor-pointer active:cursor-grabbing overflow-hidden",
        isActiveSlide || isActiveDragSource || isOverlay
          ? "border-blue-500"
          : "border-border",
        isActiveDragSource && !isOverlay && "opacity-35",
        isOverlay && "opacity-95 shadow-lg",
        className,
      )}
      style={outerStyle}
      {...props}
    >
      {showContent && (
        <div
          className="flex p-6 box-border pointer-events-none mo-slide-content overflow-hidden"
          style={{
            transform: `scale(${scale})`,
            transformOrigin: "top left",
            width: width / scale,
            height: height / scale,
          }}
        >
          <Slide cellId={cell.id} status={cell.status} output={cell.output} />
        </div>
      )}
      {isSkipped && (
        <div
          className="absolute inset-0 bg-muted/60 pointer-events-none"
          aria-hidden={true}
        />
      )}
      {visual && (
        <Tooltip
          content={
            <span className="text-xs opacity-80">{visual.description}</span>
          }
        >
          <span
            className={cn(
              "absolute top-1 right-1 flex items-center gap-1 rounded-full border p-0.5 font-medium leading-none shadow-xs cursor-help",
              isSkipped
                ? "bg-background/90 border-border text-muted-foreground"
                : "bg-background/95 border-border text-foreground/80",
            )}
            aria-label={visual.label}
          >
            <visual.Icon className="h-3.5 w-3.5" />
            {/* <span>{visual.label}</span> */}
          </span>
        </Tooltip>
      )}
    </div>
  );
};

function projectDropTarget(
  event: DragMoveEvent | DragOverEvent,
): ProjectedDropTarget | null {
  const { active, over } = event;
  if (!over) {
    return null;
  }

  const activeId = asCellId(active.id);
  const overId = asCellId(over.id);
  if (!activeId || !overId || activeId === overId) {
    return null;
  }

  const activeRect =
    active.rect.current.translated ?? active.rect.current.initial;
  if (!activeRect) {
    return null;
  }

  const pointerY = activeRect.top + activeRect.height / 2;
  const overCenter = over.rect.top + over.rect.height / 2;

  return {
    overId,
    position: pointerY < overCenter ? "before" : "after",
  };
}

function resolveDropTarget({
  cellIds,
  activeId,
  target,
}: {
  cellIds: CellIdsState;
  activeId: CellId;
  target: ProjectedDropTarget;
}): ResolvedDropTarget | null {
  if (activeId === target.overId) {
    return null;
  }
  if (cellIds.colLength !== 1) {
    Logger.warn("Multi-column mode is not supported");
    return null;
  }

  const column = cellIds.findWithId(target.overId);
  const overIndex = column.indexOfOrThrow(target.overId);

  return {
    cellId: activeId,
    columnId: column.id,
    index: target.position === "after" ? overIndex + 1 : overIndex,
  };
}

/**
 * Narrows a dnd-kit UniqueIdentifier (string | number) back to CellId.
 * Safe because we only pass CellId values as sortable item IDs.
 */
function asCellId(id: UniqueIdentifier): CellId | null {
  return typeof id === "string" ? (id as CellId) : null;
}

/**
 * Resolves the effective slide type for a cell. Falls back to `"skip"` if the
 * caller-supplied `skippedIds` set marks the cell as skipped, which keeps this
 * component working when only the legacy `skippedIds` prop is provided.
 * Returns `undefined` for the default `"slide"` type so callers can skip
 * rendering any badge.
 */
function resolveSlideType({
  cellId,
  slideTypes,
  skippedIds,
}: {
  cellId: CellId;
  slideTypes: ReadonlyMap<CellId, SlideType> | undefined;
  skippedIds: ReadonlySet<CellId> | undefined;
}): SlideType | undefined {
  const type = slideTypes?.get(cellId);
  if (type && type !== "slide") {
    return type;
  }
  if (skippedIds?.has(cellId)) {
    return "skip";
  }
  return undefined;
}

export const exportedForTesting = {
  useVisibleCellIds,
  projectDropTarget,
  resolveDropTarget,
};
