/* Copyright 2024 Marimo. All rights reserved. */
"use no memo";

import React, { memo, useMemo } from "react";
import {
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
  Table,
} from "../ui/table";
import type { Variable, Variables } from "@/core/variables/types";
import type { CellId } from "@/core/cells/ids";
import { CellLink } from "@/components/editor/links/cell-link";
import { cn } from "@/utils/cn";
import { SquareEqualIcon, WorkflowIcon } from "lucide-react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  getSortedRowModel,
  type ColumnSort,
  getFilteredRowModel,
} from "@tanstack/react-table";
import { DataTableColumnHeader } from "../data-table/column-header";
import { sortBy } from "lodash-es";
import { getCellEditorView, useCellNames } from "@/core/cells/cells";
import { goToVariableDefinition } from "@/core/codemirror/go-to-definition/commands";
import { SearchInput } from "../ui/input";
import { CellLinkList } from "../editor/links/cell-link-list";
import { VariableName } from "./common";
import { isInternalCellName } from "@/core/cells/names";

interface Props {
  className?: string;
  /**
   * Used to sort the variables.
   */
  cellIds: CellId[];
  variables: Variables;
}

interface ResolvedVariable extends Variable {
  declaredByNames: string[];
  usedByNames: string[];
}

/* Column Definitions */

function columnDefOf<T>(columnDef: ColumnDef<ResolvedVariable, T>) {
  return columnDef;
}

const ColumnIds = {
  name: "name",
  type: "type-value",
  defs: "defs-refs",
};

const COLUMNS = [
  columnDefOf({
    id: ColumnIds.name,
    accessorFn: (v) => [v.name, v.declaredBy] as const,
    enableSorting: true,
    sortingFn: "alphanumeric",
    header: ({ column }) => (
      <DataTableColumnHeader header={"Name"} column={column} />
    ),
    cell: ({ getValue }) => {
      const [name, declaredBy] = getValue();
      return <VariableName name={name} declaredBy={declaredBy} />;
    },
  }),
  columnDefOf({
    id: ColumnIds.type,
    accessorFn: (v) => [v.dataType, v.value] as const,
    enableSorting: true,
    sortingFn: "alphanumeric",
    header: ({ column }) => (
      <DataTableColumnHeader
        header={
          <div className="flex flex-col gap-1">
            <span>Type</span>
            <span>Value</span>
          </div>
        }
        column={column}
      />
    ),
    cell: ({ getValue }) => {
      const [dataType, value] = getValue();
      return (
        <div className="max-w-[150px]">
          <div className="text-ellipsis overflow-hidden whitespace-nowrap text-muted-foreground font-mono text-xs">
            {dataType}
          </div>
          <div
            className="text-ellipsis overflow-hidden whitespace-nowrap"
            title={value ?? ""}
          >
            {value}
          </div>
        </div>
      );
    },
  }),
  columnDefOf({
    id: ColumnIds.defs,
    // Include declaredByNames and usedByNames for filtering
    accessorFn: (v) =>
      [
        v.declaredBy,
        v.usedBy,
        v.name,
        v.declaredByNames,
        v.usedByNames,
      ] as const,
    enableSorting: true,
    sortingFn: "basic",
    header: ({ column }) => (
      <DataTableColumnHeader
        header={
          <div className="flex flex-col gap-1">
            <span>Declared By</span>
            <span>Used By</span>
          </div>
        }
        column={column}
      />
    ),
    cell: ({ getValue }) => {
      const [declaredBy, usedBy, name] = getValue();

      // Highlight the variable in the cell editor
      const highlightInCell = (cellId: CellId) => {
        const editorView = getCellEditorView(cellId);
        if (editorView) {
          goToVariableDefinition(editorView, name);
        }
      };

      return (
        <div className="flex flex-col gap-1 py-1">
          <div className="flex flex-row overflow-auto gap-2 items-center">
            <span title="Declared by">
              <SquareEqualIcon className="w-3.5 h-3.5 text-muted-foreground" />
            </span>

            {declaredBy.length === 1 ? (
              <CellLink
                variant="focus"
                cellId={declaredBy[0]}
                skipScroll={true}
                onClick={() => highlightInCell(declaredBy[0])}
              />
            ) : (
              <div className="text-destructive flex flex-row gap-2">
                {declaredBy.slice(0, 3).map((cellId, idx) => (
                  <span className="flex" key={cellId}>
                    <CellLink
                      variant="focus"
                      key={cellId}
                      cellId={cellId}
                      skipScroll={true}
                      className="whitespace-nowrap text-destructive"
                      onClick={() => highlightInCell(cellId)}
                    />
                    {idx < declaredBy.length - 1 && ", "}
                  </span>
                ))}
              </div>
            )}
          </div>
          <div className="flex flex-row overflow-auto gap-2 items-baseline">
            <span title="Used by">
              <WorkflowIcon className="w-3.5 h-3.5 text-muted-foreground" />
            </span>

            <CellLinkList
              maxCount={3}
              cellIds={usedBy}
              skipScroll={true}
              onClick={highlightInCell}
            />
          </div>
        </div>
      );
    },
  }),
];

/**
 * Sort the variables by the specified column sort
 * Defaults to the order they are defined in the notebook
 */
function sortData(
  variables: ResolvedVariable[],
  sort: ColumnSort | undefined,
  cellIdToIndex: Map<CellId, number>,
) {
  // Default to sort by the cell that defined it
  if (!sort) {
    sort = { id: ColumnIds.defs, desc: false };
  }

  let sortedVariables: ResolvedVariable[] = [];
  switch (sort.id) {
    case ColumnIds.name:
      sortedVariables = sortBy(variables, (v) => v.name);
      break;
    case ColumnIds.type:
      sortedVariables = sortBy(variables, (v) => v.dataType);
      break;
    case ColumnIds.defs:
      sortedVariables = sortBy(variables, (v) =>
        cellIdToIndex.get(v.declaredBy[0]),
      );
      break;
  }

  return sort.desc ? sortedVariables.reverse() : sortedVariables;
}

export const VariableTable: React.FC<Props> = memo(
  ({ className, cellIds, variables }) => {
    const [sorting, setSorting] = React.useState<SortingState>([]);
    const [globalFilter, setGlobalFilter] = React.useState("");
    const cellNames = useCellNames();

    const resolvedVariables: ResolvedVariable[] = useMemo(() => {
      const getName = (id: CellId) => {
        const name = cellNames[id];
        if (isInternalCellName(name)) {
          return `cell-${cellIds.indexOf(id)}`;
        }
        return name ?? `cell-${cellIds.indexOf(id)}`;
      };

      return Object.values(variables).map((variable) => {
        return {
          ...variable,
          declaredByNames: variable.declaredBy.map(getName),
          usedByNames: variable.usedBy.map(getName),
        };
      });
    }, [variables, cellNames, cellIds]);

    const sortedVariables = useMemo(() => {
      const cellIdToIndex = new Map<CellId, number>();
      cellIds.forEach((id, index) => cellIdToIndex.set(id, index));
      return sortData(resolvedVariables, sorting[0], cellIdToIndex);
    }, [resolvedVariables, sorting, cellIds]);

    const table = useReactTable({
      data: sortedVariables,
      columns: COLUMNS,
      getCoreRowModel: getCoreRowModel(),
      // filtering
      onGlobalFilterChange: setGlobalFilter,
      getFilteredRowModel: getFilteredRowModel(),
      enableFilters: true,
      enableGlobalFilter: true,
      enableColumnPinning: false,
      getColumnCanGlobalFilter(column) {
        // Opt-out only
        return column.columnDef.enableGlobalFilter ?? true;
      },
      globalFilterFn: "auto",
      // sorting
      manualSorting: true,
      onSortingChange: setSorting,
      getSortedRowModel: getSortedRowModel(),
      state: {
        sorting,
        globalFilter,
      },
    });

    return (
      <>
        <SearchInput
          className="w-full"
          placeholder="Search"
          value={globalFilter}
          onChange={(e) => setGlobalFilter(e.target.value)}
        />
        <Table
          className={cn(
            "w-full text-sm flex-1 border-separate border-spacing-0",
            className,
          )}
        >
          <TableHeader>
            <TableRow className="whitespace-nowrap text-xs">
              {table.getFlatHeaders().map((header) => (
                <TableHead
                  key={header.id}
                  className="sticky top-0 bg-background border-b"
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id} className="hover:bg-accent">
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className="border-b">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </>
    );
  },
);
VariableTable.displayName = "VariableTable";
