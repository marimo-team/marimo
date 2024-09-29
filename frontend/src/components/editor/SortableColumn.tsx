/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useContext } from "react";
import { mergeRefs } from "../../utils/mergeRefs";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVerticalIcon } from "lucide-react";
import { cn } from "@/utils/cn";
import { CellColumnIndex } from "@/utils/id-tree";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  columnIndex: CellColumnIndex;
}

/**
 * Context for drag handle so it can be rendered in a Slot for the column
 */
const DragHandleSlot = React.createContext<React.ReactNode>(null);

export const ColumnDragHandle: React.FC = memo(() => {
  // Slot for drag handle
  return useContext(DragHandleSlot);
});
ColumnDragHandle.displayName = "ColumnDragHandle";

const SortableColumnInternal = React.forwardRef(
  ({ columnIndex, ...props }: Props, ref: React.Ref<HTMLDivElement>) => {
    // Sort
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
    } = useSortable({ id: columnIndex });

    const style: React.CSSProperties = {
      transform: transform
        ? CSS.Transform.toString({
            x: transform.x,
            y: 0,
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
        data-testid="column-drag-button"
        className="p-3 flex flex-row justify-end cursor-grab rounded-t-lg border-2 border-b-0 hover:border-border active:bg-accent border-[var(--slate-3)]"
      >
        <GripVerticalIcon
          className="opacity-50 hover:opacity-100"
          strokeWidth={1}
          size={20}
        />
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
  }
);
SortableColumnInternal.displayName = "SortableColumn";

export const SortableColumn = memo(SortableColumnInternal);
