import { useRef } from "react";
import { ColumnDragHandle, SortableColumn } from "./SortableColumn";
import { CellColumnIndex } from "@/utils/id-tree";

interface Props {
  columnIndex: CellColumnIndex;
  children: React.ReactNode;
}

export default function Column(props: Props) {
  const columnRef = useRef<HTMLDivElement>(null);
  return (
    <SortableColumn
      tabIndex={-1}
      ref={columnRef}
      columnIndex={props.columnIndex}
    >
      <ColumnDragHandle />
      <div className="flex flex-col gap-5 w-[640px] max-w-[640px] min-w-[640px] min-h-[400px] border-2 border-[var(--slate-3)] rounded-b-lg p-6 bg-slate-50">
        {props.children}
      </div>
    </SortableColumn>
  );
}
