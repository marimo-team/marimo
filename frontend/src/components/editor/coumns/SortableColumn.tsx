/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo } from "react";
import { mergeRefs } from "../../../utils/mergeRefs";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronLeftIcon, ChevronRightIcon, X } from "lucide-react";
import type { CellColumnId } from "@/utils/id-tree";
import { useCellActions } from "@/core/cells/cells";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  columnId: CellColumnId;
  canDelete: boolean;
  canMoveLeft: boolean;
  canMoveRight: boolean;
}

const SortableColumnInternal = React.forwardRef(
  (
    { columnId, canDelete, canMoveLeft, canMoveRight, ...props }: Props,
    ref: React.Ref<HTMLDivElement>,
  ) => {
    // The keys for columns have a 1-based index, because
    // the first column is not draggable if its id is 0
    const {
      attributes,
      listeners,
      setNodeRef,
      transform,
      transition,
      isDragging,
      isOver,
    } = useSortable({ id: columnId });

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
      // @ts-expect-error  doesn't allow css variables
      "--gutter-width": "50px",
    };

    const mergedRef = mergeRefs<HTMLDivElement>(ref, setNodeRef);

    const { deleteColumn, moveColumn } = useCellActions();

    const dragHandle = (
      <div className="h-6 group flex items-center rounded-t-lg border hover:border-border border-[var(--slate-3)] overflow-hidden">
        <div className="flex gap-2 cursor-default">
          <Button
            variant="text"
            size="sm"
            className="h-full"
            onClick={() =>
              moveColumn({ column: columnId, overColumn: "_left_" })
            }
            disabled={!canMoveLeft}
          >
            <ChevronLeftIcon className="size-4" />
          </Button>
          <Button
            variant="text"
            size="sm"
            className="h-full"
            onClick={() =>
              moveColumn({ column: columnId, overColumn: "_right_" })
            }
            disabled={!canMoveRight}
          >
            <ChevronRightIcon className="size-4" />
          </Button>
        </div>
        <div
          className="flex gap-2 h-full flex-grow active:bg-accent cursor-grab"
          {...attributes}
          {...listeners}
          data-testid="column-drag-button"
        />
        {canDelete && (
          <Button
            variant="text"
            size="sm"
            className="opacity-0 group-hover:opacity-70 group-hover:hover:opacity-100 text-destructive h-full"
            onClick={() => deleteColumn({ columnId })}
          >
            <X className="size-4" />
          </Button>
        )}
      </div>
    );

    return (
      <div
        tabIndex={-1}
        ref={mergedRef}
        {...props}
        style={style}
        data-is-dragging={isDragging}
        className={cn(
          isDragging ? "" : props.className,
          // Set z-index: dragging should be above everything else
          isDragging ? "z-20" : "z-1 hover:z-10 focus-within:z-10",
          isOver && "bg-accent/20", // Add a background color when dragging over
        )}
      >
        {dragHandle}
        {props.children}
      </div>
    );
  },
);
SortableColumnInternal.displayName = "SortableColumn";

export const SortableColumn = memo(SortableColumnInternal);
