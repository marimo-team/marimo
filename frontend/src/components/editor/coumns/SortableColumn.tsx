/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useContext } from "react";
import { mergeRefs } from "../../../utils/mergeRefs";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {  ChevronLeftIcon, ChevronRightIcon, X } from "lucide-react";
import type { CellColumnIndex } from "@/utils/id-tree";
import { useCellActions } from "@/core/cells/cells";
import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  columnIndex: CellColumnIndex;
  canDelete: boolean;
  numColumns: number;
}


const SortableColumnInternal = React.forwardRef(
  ({ columnIndex, canDelete, numColumns, ...props }: Props, ref: React.Ref<HTMLDivElement>) => {
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
    const { deleteColumn, moveColumn } = useCellActions();

    const canMoveLeft = columnIndex > 0;
    const canMoveRight = columnIndex < numColumns - 1;

    const dragHandle = (
      <div
        className="h-6 group flex items-center cursor-grab rounded-t-lg border hover:border-border border-[var(--slate-3)] overflow-hidden"
      >
        <div className="flex gap-2 cursor-default">
          <Button
            variant="text"
            size="sm"
            className="h-full"
            onClick={() => moveColumn({ column: columnIndex, overColumn: (columnIndex - 1) as CellColumnIndex })}
            disabled={!canMoveLeft}
          >
            <ChevronLeftIcon className="size-4" />
          </Button>
          <Button
            variant="text"
            size="sm"
            className="h-full"
            onClick={() => moveColumn({ column: columnIndex, overColumn: (columnIndex + 1) as CellColumnIndex })}
            disabled={!canMoveRight}
          >
            <ChevronRightIcon className="size-4" />
          </Button>
        </div>
        <div className="flex gap-2 h-full flex-grow bg-red-500 active:bg-accent"
                {...attributes}
                {...listeners}
                data-testid="column-drag-button"
        />
          {canDelete && (
            <Button
            variant="text"
            size="sm"
            className="opacity-0 group-hover:opacity-70 group-hover:hover:opacity-100 text-destructive h-full"
            onClick={() => deleteColumn({ columnIndex })}
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
          isDragging ? "z-20" : "hover:z-10"
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
