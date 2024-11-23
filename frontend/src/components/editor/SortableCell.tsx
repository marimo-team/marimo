/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useContext } from "react";
import { mergeRefs } from "../../utils/mergeRefs";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVerticalIcon } from "lucide-react";
import type { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";
import { Events } from "@/utils/events";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  cellId: CellId;
  canMoveX?: boolean;
}

/**
 * Context for drag handle so it can be rendered in a Slot in the cell
 */
const DragHandleSlot = React.createContext<React.ReactNode>(null);

export const CellDragHandle: React.FC = memo(() => {
  // Slot for drag handle
  return useContext(DragHandleSlot);
});
CellDragHandle.displayName = "DragHandle";

const SortableCellInternal = React.forwardRef(
  ({ cellId, canMoveX, ...props }: Props, ref: React.Ref<HTMLDivElement>) => {
    // Sort
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: cellId.toString() });

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

    const mergedRef = mergeRefs<HTMLDivElement>(ref, setNodeRef);

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
        ref={mergedRef}
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
          {props.children}
        </DragHandleSlot.Provider>
      </div>
    );
  },
);
SortableCellInternal.displayName = "SortableCell";

export const SortableCell = memo(SortableCellInternal);
