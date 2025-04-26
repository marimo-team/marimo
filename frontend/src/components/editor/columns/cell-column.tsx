/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { memo, useRef, useCallback } from "react";
import { SortableColumn } from "./sortable-column";
import type { CellColumnId } from "@/utils/id-tree";
import type { AppConfig } from "@/core/config/config-schema";
import useResizeObserver, { type ObservedSize } from "use-resize-observer";
import { storage } from "./storage";
import { getColumnWidth } from "./storage";

interface Props {
  className?: string;
  columnId: CellColumnId;
  children: React.ReactNode;
  width: AppConfig["width"];
  footer?: React.ReactNode;
  canDelete: boolean;
  canMoveLeft: boolean;
  canMoveRight: boolean;
}

export const Column = memo((props: Props) => {
  const columnRef = useRef<HTMLDivElement>(null);
  const resizableDivRef = useRef<HTMLDivElement>(null);
  const debounceTimeoutRef = useRef<NodeJS.Timeout>();
  const startingWidth = getColumnWidth(props.columnId);

  const onResize = useCallback((size: ObservedSize) => {
    if (!resizableDivRef.current) {
      return;
    }

    const width = size.width ?? startingWidth;

    // Clear any existing timeout
    if (debounceTimeoutRef.current) {
      clearTimeout(debounceTimeoutRef.current);
    }

    // Set a new timeout to save after 500ms of no changes
    debounceTimeoutRef.current = setTimeout(() => {
      storage.set({
        colToWidth: { ...storage.get().colToWidth, [props.columnId]: width },
      });
    }, 500);
  }, []);

  const { width, height } = useResizeObserver({
    ref: resizableDivRef,
    onResize: onResize,
  });
  console.log("width", width, "height", height);

  const widthClass =
    typeof startingWidth === "string" ? startingWidth : `${startingWidth}px`;

  const column = (
    <div
      ref={resizableDivRef}
      className={cn(
        "flex flex-col gap-5",
        // box-content is needed so the column is width=contentWidth, but not affected by padding
        props.width === "columns" &&
          "w-contentWidth box-content min-h-[100px] px-11 py-6 overflow-hidden resize-x",
      )}
      style={{ width: widthClass }}
    >
      {props.children}
    </div>
  );

  if (props.width === "columns") {
    return (
      <SortableColumn
        tabIndex={-1}
        ref={columnRef}
        canDelete={props.canDelete}
        columnId={props.columnId}
        canMoveLeft={props.canMoveLeft}
        canMoveRight={props.canMoveRight}
        className="group/column"
      >
        {column}
        {props.footer}
      </SortableColumn>
    );
  }

  return (
    <>
      {column}
      {props.footer}
    </>
  );
});

Column.displayName = "Column";
