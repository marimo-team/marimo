/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { memo, useRef } from "react";
import { SortableColumn } from "./sortable-column";
import type { CellColumnId } from "@/utils/id-tree";
import type { AppConfig } from "@/core/config/config-schema";

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

  const column = (
    <div
      className={cn(
        "flex flex-col gap-5",
        // box-content is needed so the column is width=contentWidth, but not affected by padding
        props.width === "columns" &&
          "w-contentWidth box-content	 min-h-[100px] border border-t-0 border-[var(--slate-3)] rounded-b-lg px-11 py-6 bg-[var(--slate-2)]",
      )}
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
