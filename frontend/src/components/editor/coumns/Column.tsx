/* Copyright 2024 Marimo. All rights reserved. */
import { cn } from "@/utils/cn";
import { useRef } from "react";
import { SortableColumn } from "./SortableColumn";
import type { CellColumnIndex } from "@/utils/id-tree";

interface Props {
  className?: string;
  columnIndex: CellColumnIndex;
  children: React.ReactNode;
  width: string;
  canDelete: boolean;
  footer?: React.ReactNode;
  numColumns: number;
}

export const Column = (props: Props) => {
  const columnRef = useRef<HTMLDivElement>(null);

  const column = <div
  className={cn(
    "flex flex-col gap-5",
    props.width === "columns" &&
      "w-contentWidth min-h-[400px] border border-t-0 border-[var(--slate-3)] rounded-b-lg p-6 bg-background",
  )}
>
    {props.children}
  </div>

  if (props.width === "columns") {
    return <SortableColumn
      tabIndex={-1}
      ref={columnRef}
      canDelete={props.canDelete}
      columnIndex={props.columnIndex}
      numColumns={props.numColumns}
      className="group/column"
    >
      {column}
      {props.footer}
    </SortableColumn>
  }

  return column;
};
