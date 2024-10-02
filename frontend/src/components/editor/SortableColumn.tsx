/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useContext } from "react";
import { mergeRefs } from "../../utils/mergeRefs";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVerticalIcon, X } from "lucide-react";
import { cn } from "@/utils/cn";
import type { CellColumnIndex } from "@/utils/id-tree";
import { useCellActions } from "@/core/cells/cells";

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
    // The keys for columns have a 1-based index, because
    // the first column is not draggable if its id is 0
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

    columnIndex = (columnIndex - 1) as CellColumnIndex;
    const { deleteColumnBreakpoint } = useCellActions();

    const dragHandle = (
      <div
        {...attributes}
        {...listeners}
        data-testid="column-drag-button"
        className="group p-3 flex flex-row justify-end cursor-grab rounded-t-lg border-2 border-b-0 hover:border-border active:bg-accent border-[var(--slate-3)]"
      >
        {columnIndex > 0 && (
          <X
            className="opacity-0 group-hover:opacity-100 me-2 cursor-pointer"
            strokeWidth={1}
            size={20}
            onClick={() => deleteColumnBreakpoint({ columnIndex })}
          />
        )}
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
  },
);
SortableColumnInternal.displayName = "SortableColumn";

export const SortableColumn = memo(SortableColumnInternal);
