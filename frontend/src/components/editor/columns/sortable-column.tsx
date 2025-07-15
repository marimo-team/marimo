/* Copyright 2024 Marimo. All rights reserved. */

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ChevronLeftIcon, ChevronRightIcon, PlusIcon, X } from "lucide-react";
import React, { memo } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useCellActions } from "@/core/cells/cells";
import { cn } from "@/utils/cn";
import type { CellColumnId } from "@/utils/id-tree";
import { mergeRefs } from "../../../utils/mergeRefs";

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

    const { deleteColumn, moveColumn, addColumn } = useCellActions();

    const buttonClasses = cn("h-full hover:bg-muted rounded-none");

    const handleScrollAppRight = () => {
      const app = document.getElementById("App");
      if (app) {
        app.scrollTo({
          left: app.scrollLeft + 1000,
          behavior: "smooth",
        });
      }
    };

    const dragHandle = (
      <div className="h-6 group flex items-center rounded-t-lg border hover:border-border border-[var(--slate-3)] overflow-hidden bg-[var(--slate-1)]">
        <Tooltip content="Move column left" side="top" delayDuration={300}>
          <Button
            variant="text"
            size="sm"
            className={buttonClasses}
            onClick={() =>
              moveColumn({ column: columnId, overColumn: "_left_" })
            }
            disabled={!canMoveLeft}
          >
            <ChevronLeftIcon className="size-4" />
          </Button>
        </Tooltip>
        <Tooltip content="Move column right" side="top" delayDuration={300}>
          <Button
            variant="text"
            size="sm"
            className={buttonClasses}
            onClick={() =>
              moveColumn({ column: columnId, overColumn: "_right_" })
            }
            disabled={!canMoveRight}
          >
            <ChevronRightIcon className="size-4" />
          </Button>
        </Tooltip>
        <div
          className="flex gap-2 h-full flex-grow active:bg-accent cursor-grab"
          {...attributes}
          {...listeners}
          data-testid="column-drag-button"
        />
        {canDelete && (
          <Tooltip content="Delete column" side="top" delayDuration={300}>
            <Button
              variant="text"
              size="sm"
              className="opacity-0 group-hover:opacity-70 group-hover:hover:opacity-100 text-destructive h-full hover:bg-destructive/20 rounded-none"
              onClick={() => deleteColumn({ columnId })}
            >
              <X className="size-4" />
            </Button>
          </Tooltip>
        )}
        <Tooltip content="Add column" side="top" delayDuration={300}>
          <Button
            variant="text"
            size="sm"
            className={buttonClasses}
            onClick={() => {
              addColumn({ columnId });
              requestAnimationFrame(handleScrollAppRight);
            }}
          >
            <PlusIcon className="size-4" />
          </Button>
        </Tooltip>
      </div>
    );

    return (
      <div
        tabIndex={-1}
        ref={(r) => {
          mergeRefs(ref, setNodeRef)(r);
        }}
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
