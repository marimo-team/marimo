/* Copyright 2026 Marimo. All rights reserved. */

import React, { memo, useRef } from "react";
import type { AppConfig } from "@/core/config/config-schema";
import { useResizeHandle } from "@/hooks/useResizeHandle";
import { cn } from "@/utils/cn";
import type { CellColumnId } from "@/utils/id-tree";
import { SortableColumn } from "./sortable-column";
import { storageFn } from "./storage";

interface Props {
  className?: string;
  columnId: CellColumnId;
  index: number;
  children: React.ReactNode;
  width: AppConfig["width"];
  footer?: React.ReactNode;
  canDelete: boolean;
  canMoveLeft: boolean;
  canMoveRight: boolean;
  /**
   * If true, column chrome (drag handles, resize handles, borders) is hidden
   * while keeping the same component tree mounted.
   */
  presenting?: boolean;
}

const { getColumnWidth, saveColumnWidth } = storageFn;

export const Column = memo((props: Props) => {
  const columnRef = useRef<HTMLDivElement>(null);

  // Published cells are not spaced apart. Set once on the column root; the
  // CSS variable cascades to the gap-using descendants.
  const zeroGapWhenPresenting = props.presenting && "[--notebook-cell-gap:0px]";

  if (props.width === "columns") {
    return (
      <SortableColumn
        tabIndex={-1}
        ref={columnRef}
        canDelete={props.canDelete}
        columnId={props.columnId}
        canMoveLeft={props.canMoveLeft}
        canMoveRight={props.canMoveRight}
        className={cn("group/column", zeroGapWhenPresenting)}
        footer={props.footer}
        presenting={props.presenting}
      >
        <ResizableComponent
          startingWidth={getColumnWidth(props.index)}
          onResize={(width: number) => {
            saveColumnWidth(props.index, width);
          }}
          presenting={props.presenting}
        >
          {props.children}
        </ResizableComponent>
      </SortableColumn>
    );
  }

  return (
    <>
      <div
        data-testid="cell-column"
        className={cn(
          "flex flex-col gap-(--notebook-cell-gap)",
          zeroGapWhenPresenting,
        )}
      >
        {props.children}
      </div>
      {props.footer}
    </>
  );
});

Column.displayName = "Column";

interface ResizableComponentProps {
  startingWidth: number | "contentWidth";
  onResize?: (width: number) => void;
  children: React.ReactNode;
  presenting?: boolean;
}

const ResizableComponent = ({
  startingWidth,
  onResize,
  children,
  presenting,
}: ResizableComponentProps) => {
  const { resizableDivRef, handleRefs, style } = useResizeHandle({
    startingWidth,
    onResize,
  });

  const renderResizeHandler = (ref: React.RefObject<HTMLDivElement | null>) => {
    return (
      <div
        ref={ref}
        data-testid="column-resize-handle"
        className={`w-[3px] cursor-col-resize transition-colors duration-200 z-100
          relative before:content-[''] before:absolute before:inset-y-0 before:left-[-3px]
          before:right-[-3px] before:w-[9px] before:z-[-1]
          hover/column:bg-[var(--slate-3)] dark:hover/column:bg-[var(--slate-5)]
          hover/column:hover:bg-primary/60 dark:hover/column:hover:bg-primary/60`}
        hidden={presenting}
      />
    );
  };

  return (
    <div className="flex flex-row">
      {renderResizeHandler(handleRefs.left)}
      <div
        ref={resizableDivRef}
        className={cn(
          "flex flex-col gap-(--notebook-cell-gap) box-content z-1",
          // While presenting, use the published content width instead of the
          // editor geometry (saved pixel width, 500px minimum, gutters),
          // which overflows narrow screens.
          presenting
            ? "w-(--content-width)"
            : "min-h-[100px] px-11 pt-3 pb-6 min-w-[500px]",
        )}
        style={presenting ? undefined : style}
      >
        {children}
      </div>
      {renderResizeHandler(handleRefs.right)}
    </div>
  );
};
