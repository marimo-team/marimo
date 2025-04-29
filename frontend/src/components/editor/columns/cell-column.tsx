/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useRef } from "react";
import { SortableColumn } from "./sortable-column";
import type { CellColumnId } from "@/utils/id-tree";
import type { AppConfig } from "@/core/config/config-schema";
import { storageFn } from "./storage";
import { useResizeHandle } from "@/hooks/useResizeHandle";

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
}

const { getColumnWidth, setColumnWidth } = storageFn;

export const Column = memo((props: Props) => {
  const columnRef = useRef<HTMLDivElement>(null);

  const column: React.ReactNode =
    props.width === "columns" ? (
      <ResizableComponent
        startingWidth={getColumnWidth(props.index)}
        onResize={(width: number) => {
          setColumnWidth(props.index, width);
        }}
      >
        {props.children}
      </ResizableComponent>
    ) : (
      <div className="flex flex-col gap-5">{props.children}</div>
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

interface ResizableComponentProps {
  startingWidth: number | "contentWidth";
  onResize?: (width: number) => void;
  children: React.ReactNode;
}

const ResizableComponent = ({
  startingWidth,
  onResize,
  children,
}: ResizableComponentProps) => {
  const { resizableDivRef, handleRef, style } = useResizeHandle({
    startingWidth,
    onResize,
  });

  return (
    <div className="flex flex-row gap-2">
      <div
        ref={resizableDivRef}
        className="flex flex-col gap-5 box-content min-h-[100px] px-11 py-6 min-w-[500px] z-1"
        style={style}
      >
        {children}
      </div>
      <div
        ref={handleRef}
        className="w-1 cursor-col-resize transition-colors duration-200 z-10
        group-hover/column:bg-[var(--slate-3)] dark:group-hover/column:bg-[var(--slate-5)]
        group-hover/column:hover:bg-primary/60 dark:group-hover/column:hover:bg-primary/60"
      />
    </div>
  );
};
