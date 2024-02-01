/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useContext } from "react";
import { mergeRefs } from "../../utils/mergeRefs";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVerticalIcon } from "lucide-react";
import { CellId } from "@/core/cells/ids";
import { cn } from "@/utils/cn";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  cellId: CellId;
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
  ({ cellId, ...props }: Props, ref: React.Ref<HTMLDivElement>) => {
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
            // No x-transform since only sorting in the y-axis
            x: 0,
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
        data-testid="drag-button"
        className="py-[1px] mx-2 cursor-grab opacity-50 hover:opacity-100 hover-action hover:bg-muted rounded border border-transparent hover:border-border active:bg-accent"
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
        className={cn(props.className, isMoving && "is-moving")}
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
