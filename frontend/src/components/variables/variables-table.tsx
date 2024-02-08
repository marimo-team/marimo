/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo, useMemo } from "react";
import {
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
  Table,
} from "../ui/table";
import { Variable, Variables } from "@/core/variables/types";
import { CellId } from "@/core/cells/ids";
import { CellLink } from "@/components/editor/links/cell-link";
import { cn } from "@/utils/cn";
import { SquareEqualIcon, WorkflowIcon } from "lucide-react";
import { Badge } from "../ui/badge";
import { toast } from "../ui/use-toast";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  ColumnDef,
  SortingState,
  getSortedRowModel,
  ColumnSort,
} from "@tanstack/react-table";
import { DataTableColumnHeader } from "../data-table/column-header";
import { sortBy } from "lodash-es";
import { getCellEditorView } from "@/core/cells/cells";
import { goToDefinition } from "@/core/codemirror/find-replace/search-highlight";

interface Props {
  className?: string;
  /**
   * Used to sort the variables.
   */
  cellIds: CellId[];
  variables: Variables;
}

/* Column Definitions */

function columnDefOf<T>(columnDef: ColumnDef<Variable, T>) {
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
      return (
        <div className="max-w-[130px]">
          <Badge
            title={name}
            variant={declaredBy.length > 1 ? "destructive" : "outline"}
            className="rounded-sm text-ellipsis block overflow-hidden max-w-fit cursor-pointer font-medium"
            onClick={() => {
              navigator.clipboard.writeText(name);
              toast({ title: "Copied to clipboard" });
            }}
          >
            {name}
          </Badge>
        </div>
      );
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
            title={value}
          >
            {value}
          </div>
        </div>
      );
    },
  }),
  columnDefOf({
    id: ColumnIds.defs,
    accessorFn: (v) => [v.declaredBy, v.usedBy, v.name] as const,
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
          goToDefinition(editorView, name);
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

            {usedBy.slice(0, 3).map((cellId, idx) => (
              <span className="flex" key={cellId}>
                <CellLink
                  variant="focus"
                  key={cellId}
                  cellId={cellId}
                  className="whitespace-nowrap"
                  onClick={() => highlightInCell(cellId)}
                />
                {idx < usedBy.length - 1 && ", "}
              </span>
            ))}
            {usedBy.length > 3 && (
              <div className="whitespace-nowrap text-muted-foreground text-xs">
                +{usedBy.length - 3} more
              </div>
            )}
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
  variables: Variable[],
  sort: ColumnSort | undefined,
  cellIdToIndex: Map<CellId, number>,
) {
  // Default to sort by the cell that defined it
  if (!sort) {
    sort = { id: ColumnIds.defs, desc: false };
  }

  let sortedVariables: Variable[] = [];
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

    const sortedVariables = useMemo(() => {
      const cellIdToIndex = new Map<CellId, number>();
      cellIds.forEach((id, index) => cellIdToIndex.set(id, index));
      return sortData(Object.values(variables), sorting[0], cellIdToIndex);
    }, [variables, sorting, cellIds]);

    const table = useReactTable({
      data: sortedVariables,
      columns: COLUMNS,
      getCoreRowModel: getCoreRowModel(),
      // sorting
      manualSorting: true,
      onSortingChange: setSorting,
      getSortedRowModel: getSortedRowModel(),
      state: { sorting },
    });

    return (
      <Table className={cn("w-full overflow-hidden text-sm flex-1", className)}>
        <TableHeader>
          <TableRow className="whitespace-nowrap text-xs">
            {table.getFlatHeaders().map((header) => (
              <TableHead key={header.id}>
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
                <TableCell key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  },
);
VariableTable.displayName = "VariableTable";
