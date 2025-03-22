/* Copyright 2024 Marimo. All rights reserved. */
import type {
  TableFeature,
  RowData,
  Table,
  Column,
} from "@tanstack/react-table";
import type { ColumnChartingTableState, ColumnChartingOptions } from "./types";
import {
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuPortal,
  DropdownMenuItem,
  DropdownMenuSubContent,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ChartBarIcon } from "lucide-react";
import { NAMELESS_COLUMN_PREFIX } from "../columns";
import { maybeAddAltairImport } from "@/core/cells/add-missing-import";
import { useCellActions } from "@/core/cells/cells";
import { useLastFocusedCellId } from "@/core/cells/focus";
import { autoInstantiateAtom } from "@/core/config/config";
import { useAtomValue } from "jotai";

const iconClassName = "mr-2 h-3.5 w-3.5 text-muted-foreground/70";

export const ColumnChartingFeature: TableFeature = {
  getInitialState: (state): ColumnChartingTableState => {
    return {
      ...state,
    };
  },

  getDefaultOptions: <TData extends RowData>(
    table: Table<TData>,
  ): ColumnChartingOptions => {
    return {
      enableColumnCharting: false,
      tableName: "",
    } as ColumnChartingOptions;
  },

  createColumn: <TData extends RowData>(
    column: Column<TData>,
    table: Table<TData>,
  ) => {
    if (!table.options.tableName) {
      return null;
    }

    const id = column.id;
    if (id.startsWith(NAMELESS_COLUMN_PREFIX)) {
      return null;
    }

    const dataType = column.columnDef.meta?.dataType;
    if (!dataType) {
      return null;
    }

    const isNumeric = dataType === "number" || dataType === "integer";
    const isDate = dataType === "date" || dataType === "datetime";
    if (!isNumeric && !isDate) {
      return null;
    }

    column.renderChartMenuItems = () => {
      return <ChartingMenuItems column={column} table={table} />;
    };
  },
};

const ChartingMenuItems = <TData extends RowData>(props: {
  column: Column<TData>;
  table: Table<TData>;
}) => {
  const { createNewCell } = useCellActions();
  const lastFocusedCellId = useLastFocusedCellId();
  const autoInstantiate = useAtomValue(autoInstantiateAtom);

  const otherColumns = props.table
    .getAllColumns()
    .filter((c) => c.id !== props.column.id)
    .sort();

  const handleInsertCode = (xAxis: string, yAxis: string) => {
    maybeAddAltairImport(autoInstantiate, createNewCell, lastFocusedCellId);

    const tableName = props.table.options.tableName;
    const altairCode = `
alt.Chart(${tableName}).mark_bar().encode(
  x=alt.X("${xAxis}"),
  y=alt.Y("${yAxis}")
)`.trim();
    createNewCell({
      code: altairCode,
      before: false,
      cellId: lastFocusedCellId ?? "__end__",
    });
  };

  return (
    <>
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          <ChartBarIcon className={iconClassName} />
          Chart on X axis
        </DropdownMenuSubTrigger>
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <div className="flex flex-col gap-2">Chart on Y axis</div>
            <DropdownMenuSeparator />
            {otherColumns.map((c) => (
              <DropdownMenuItem
                key={c.id}
                onSelect={() => handleInsertCode(props.column.id, c.id)}
              >
                {c.id} ({c.columnDef.meta?.dtype})
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
      <DropdownMenuSub>
        <DropdownMenuSubTrigger>
          <ChartBarIcon className={iconClassName} />
          Chart on Y axis
        </DropdownMenuSubTrigger>
        <DropdownMenuPortal>
          <DropdownMenuSubContent>
            <div className="flex flex-col gap-2">Chart on X axis</div>
            <DropdownMenuSeparator />
            {otherColumns.map((c) => (
              <DropdownMenuItem
                key={c.id}
                onSelect={() => handleInsertCode(props.column.id, c.id)}
              >
                {c.id} ({c.columnDef.meta?.dtype})
              </DropdownMenuItem>
            ))}
          </DropdownMenuSubContent>
        </DropdownMenuPortal>
      </DropdownMenuSub>
      <DropdownMenuSeparator />
    </>
  );
};
