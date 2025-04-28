/* Copyright 2024 Marimo. All rights reserved. */
import { memo, useEffect, useRef } from "react";
import { SortableColumn } from "./sortable-column";
import type { CellColumnId } from "@/utils/id-tree";
import type { AppConfig } from "@/core/config/config-schema";
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
}

export const Column = memo((props: Props) => {
  const columnRef = useRef<HTMLDivElement>(null);
  const resizableDivRef = useRef<HTMLDivElement>(null);
  const rightHandleRef = useRef<HTMLDivElement>(null);

  const { getColumnWidth, setColumnWidth } = storageFn;
  const startingWidth = getColumnWidth(props.index);

  useEffect(() => {
    if (!rightHandleRef.current || !resizableDivRef.current) {
      return;
    }
    const handleRef = rightHandleRef.current;

    let width = Number.parseInt(
      window.getComputedStyle(resizableDivRef.current).width,
      10,
    );
    let lastX = 0;

    // Right handle
    const onMouseMoveRight = (e: MouseEvent) => {
      if (!resizableDivRef.current) {
        return;
      }
      const dx = e.clientX - lastX;
      lastX = e.clientX;
      width += dx;
      resizableDivRef.current.style.width = `${width}px`;

      // const viewportWidth = window.innerWidth;
      // if (e.clientX > viewportWidth - 100) {
      //   const appContainer = document.getElementById("App");
      //   if (appContainer) {
      //     appContainer.scrollLeft += 10;
      //   }
      // }
    };

    const onMouseUp = (e: MouseEvent) => {
      setColumnWidth(props.index, width);
      document.removeEventListener("mousemove", onMouseMoveRight);
    };

    const onMouseRightDown = (e: MouseEvent) => {
      lastX = e.clientX;
      document.addEventListener("mousemove", onMouseMoveRight);
      document.addEventListener("mouseup", onMouseUp);
    };

    handleRef.addEventListener("mousedown", onMouseRightDown);

    return () => {
      handleRef.removeEventListener("mousedown", onMouseRightDown);
    };
  }, [props.index, setColumnWidth]);

  let column = null;
  column =
    props.width === "columns" ? (
      <div className="flex flex-row gap-2">
        <div
          ref={resizableDivRef}
          className="flex flex-col gap-5 box-content min-h-[100px] px-11 py-6 min-w-[500px]"
          style={{
            width:
              typeof startingWidth === "string"
                ? startingWidth
                : `${startingWidth}px`,
          }}
        >
          {props.children}
        </div>
        <div
          ref={rightHandleRef}
          className="w-0.5 px-[2px] group-hover/column:bg-[var(--slate-2)] cursor-col-resize"
        />
      </div>
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
