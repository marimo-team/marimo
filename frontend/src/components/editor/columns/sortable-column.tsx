/* Copyright 2026 Marimo. All rights reserved. */

import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  AlertCircleIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ClockIcon,
  GripHorizontal,
  Loader2Icon,
  MoreHorizontal,
  PauseCircleIcon,
  PlusIcon,
  RefreshCcwIcon,
  X,
} from "lucide-react";
import React, { memo } from "react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { useCellActions } from "@/core/cells/cells";
import type { CellStateSummary } from "@/core/cells/semantic-state";
import { cn } from "@/utils/cn";
import type { CellColumnId } from "@/utils/id-tree";
import { mergeRefs } from "../../../utils/mergeRefs";

interface Props extends React.HTMLAttributes<HTMLDivElement> {
  columnId: CellColumnId;
  canDelete: boolean;
  canMoveLeft: boolean;
  canMoveRight: boolean;
  footer?: React.ReactNode;
  statusSummary?: CellStateSummary;
  /**
   * If true, dragging is disabled and the column chrome is hidden
   * (e.g. while presenting).
   */
  presenting?: boolean;
}

const SortableColumnInternal = React.forwardRef(
  (
    {
      columnId,
      canDelete,
      canMoveLeft,
      canMoveRight,
      footer,
      presenting,
      statusSummary,
      ...props
    }: Props,
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
    } = useSortable({ id: columnId, disabled: presenting });

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

    const buttonClasses = "hover:bg-(--gray-3) aspect-square p-0 w-7 h-7";

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
      <div
        data-testid="column-header"
        className="px-2 pb-0 group flex items-center overflow-hidden border-b border-(--slate-7)"
        hidden={presenting}
      >
        <Tooltip content="Move column left" side="top" delayDuration={300}>
          <Button
            variant="text"
            size="xs"
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
            size="xs"
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
          className="flex gap-2 h-full grow cursor-grab active:cursor-grabbing items-center justify-center"
          data-testid="column-drag-spacer"
          {...attributes}
          {...listeners}
        >
          <GripHorizontal className="size-4 opacity-0 group-hover:opacity-50 transition-opacity duration-200" />
        </div>
        <ColumnStateSummary summary={statusSummary} />
        <DropdownMenu>
          <DropdownMenuTrigger asChild={true}>
            <Button variant="text" size="xs" className={buttonClasses}>
              <MoreHorizontal className="size-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem
              onClick={() => deleteColumn({ columnId })}
              disabled={!canDelete}
            >
              <X className="mr-2 size-4" />
              Delete column
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Tooltip content="Add column" side="top" delayDuration={300}>
          <Button
            variant="text"
            size="xs"
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
        <div
          data-testid="column-frame"
          className={cn(!presenting && "border border-(--slate-7)")}
        >
          {dragHandle}
          {props.children}
        </div>
        {footer}
      </div>
    );
  },
);
SortableColumnInternal.displayName = "SortableColumn";

export const SortableColumn = memo(SortableColumnInternal);

const ColumnStateSummary = ({ summary }: { summary?: CellStateSummary }) => {
  if (!summary) {
    return null;
  }

  const items = [
    {
      count: summary.running,
      label: "running",
      icon: <Loader2Icon className="size-3 animate-spin text-(--blue-10)" />,
    },
    {
      count: summary.queued,
      label: "queued",
      icon: <ClockIcon className="size-3 text-(--blue-10)" />,
    },
    {
      count: summary.pending,
      label: "need execution",
      icon: <RefreshCcwIcon className="size-3 text-(--slate-10)" />,
    },
    {
      count: summary.failed,
      label: "failed",
      icon: <AlertCircleIcon className="size-3 text-(--red-10)" />,
    },
    {
      count: summary.unavailableOutdated,
      label: "outdated but unavailable",
      icon: <PauseCircleIcon className="size-3 text-(--slate-10)" />,
    },
  ].filter((item) => item.count > 0);

  if (items.length === 0) {
    return null;
  }

  const statusLabel = items
    .map(({ count, label }) => `${count} ${label}`)
    .join(", ");

  return (
    <div
      role="status"
      aria-label={`Column status: ${statusLabel}`}
      className="flex items-center gap-1 pr-1"
    >
      {items.map(({ count, label, icon }) => (
        <Tooltip
          key={label}
          content={`${count} ${label}`}
          side="top"
          delayDuration={300}
        >
          <span className="inline-flex items-center gap-0.5 text-xs tabular-nums text-(--slate-11)">
            {icon}
            {count}
          </span>
        </Tooltip>
      ))}
    </div>
  );
};
