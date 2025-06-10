/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, use } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS, type Transform } from "@dnd-kit/utilities";
import { GripVerticalIcon } from "lucide-react";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";
import { mergeRefs } from "@/utils/mergeRefs";
import type { SyntheticListenerMap } from "@dnd-kit/core/dist/hooks/utilities";
import type { DraggableAttributes } from "@dnd-kit/core";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  cellId: CellId;
  canMoveX?: boolean;
}

/**
 * Context for drag handle so it can be rendered in a Slot in the cell
 */
const DragHandleSlot = React.createContext<React.ReactNode>(null);

export const CellDragHandle: React.FC = memo(() => {
  // Slot for drag handle
  return use(DragHandleSlot);
});
CellDragHandle.displayName = "DragHandle";

function isTransformNoop(transform: Transform | null) {
  if (!transform) {
    return true;
  }
  return (
    transform.x === 0 &&
    transform.y === 0 &&
    transform.scaleX === 1 &&
    transform.scaleY === 1
  );
}

export const SortableCell = React.forwardRef(
  (
    { cellId, canMoveX, ...props }: Props,
    ref: React.ForwardedRef<HTMLDivElement>,
  ) => {
    // This hook re-renders every time _any_ cell is dragged,
    // so we should avoid any expensive operations in this component
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: cellId.toString() });

    // Perf:
    // If the transform is a noop, keep it as null
    const transformOrNull = isTransformNoop(transform) ? null : transform;
    // If there is no transform, we don't need a transition
    const transitionOrUndefined =
      transformOrNull == null ? undefined : transition;

    // Use a new component to avoid re-rendering when the cell is dragged
    return (
      <SortableCellInternal
        ref={ref}
        cellId={cellId}
        canMoveX={canMoveX}
        {...props}
        attributes={attributes}
        listeners={listeners}
        setNodeRef={setNodeRef}
        transform={transformOrNull}
        transition={transitionOrUndefined}
        isDragging={isDragging}
      />
    );
  },
);
SortableCell.displayName = "SortableCell";

interface SortableCellInternalProps extends Props {
  children: React.ReactNode;
  attributes: DraggableAttributes;
  listeners: SyntheticListenerMap | undefined;
  setNodeRef: (node: HTMLElement | null) => void;
  transform: Transform | null;
  transition: string | undefined;
  isDragging: boolean;
}

const SortableCellInternal = React.forwardRef(
  (
    {
      cellId,
      canMoveX,
      children,
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
      ...props
    }: SortableCellInternalProps,
    ref: React.ForwardedRef<HTMLDivElement>,
  ) => {
    const style: React.CSSProperties = {
      transform: transform
        ? CSS.Transform.toString({
            x: canMoveX ? transform.x : 0,
            y: transform.y,
            scaleX: 1,
            scaleY: 1,
          })
        : undefined,
      transition,
      zIndex: isDragging ? 2 : undefined,
      position: "relative",
    };

    const dragHandle = (
      <div
        {...attributes}
        {...listeners}
        onMouseDown={Events.preventFocus}
        data-testid="drag-button"
        className="py-[1px] cursor-grab opacity-50 hover:opacity-100 hover-action hover:bg-muted rounded border border-transparent hover:border-border active:bg-accent"
      >
        <GripVerticalIcon strokeWidth={1} size={20} />
      </div>
    );

    const isMoving = Boolean(transform);

    return (
      <div
        tabIndex={-1}
        ref={(r) => {
          mergeRefs<HTMLDivElement>(ref, setNodeRef)(r);
        }}
        {...props}
        data-is-dragging={isDragging}
        className={cn(
          props.className,
          isMoving && "is-moving",
          "outline-offset-4 outline-primary/40 rounded-lg",
        )}
        style={style}
      >
        <DragHandleSlot.Provider value={dragHandle}>
          {children}
        </DragHandleSlot.Provider>
      </div>
    );
  },
);
SortableCellInternal.displayName = "SortableCellInternal";
