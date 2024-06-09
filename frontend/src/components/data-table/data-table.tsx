/* Copyright 2024 Marimo. All rights reserved. */
import React, { memo } from "react";
import {
  ColumnDef,
  OnChangeFn,
  PaginationState,
  RowSelectionState,
  SortingState,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DataTablePagination } from "./pagination";
import { DownloadActionProps, DownloadAs } from "./download-actions";
import { cn } from "@/utils/cn";

interface DataTableProps<TData> extends Partial<DownloadActionProps> {
  wrapperClassName?: string;
  className?: string;
  columns: Array<ColumnDef<TData>>;
  data: TData[];
  sorting?: SortingState;
  setSorting?: OnChangeFn<SortingState>;
  pagination?: boolean;
  pageSize?: number;
  selection?: "single" | "multi" | null;
  showColumnSummary?: boolean;
  rowSelection?: RowSelectionState;
  onRowSelectionChange?: OnChangeFn<RowSelectionState>;
}

const DataTableInternal = <TData,>({
  wrapperClassName,
  className,
  columns,
  data,
  sorting,
  setSorting,
  rowSelection,
  pageSize = 10,
  downloadAs,
  pagination = false,
  onRowSelectionChange,
}: DataTableProps<TData>) => {
  const [paginationState, setPaginationState] = React.useState<PaginationState>(
    { pageSize: pageSize, pageIndex: 0 },
  );

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    // pagination
    onPaginationChange: setPaginationState,
    getPaginationRowModel: pagination ? getPaginationRowModel() : undefined,
    // sorting
    onSortingChange: setSorting,
    manualSorting: true,
    getSortedRowModel: getSortedRowModel(),
    // selection
    onRowSelectionChange: onRowSelectionChange,
    state: {
      sorting,
      pagination: pagination
        ? { ...paginationState, pageSize: pageSize }
        : { pageIndex: 0, pageSize: data.length },
      rowSelection,
    },
  });

  return (
    <div className={cn(wrapperClassName, "flex flex-col space-y-2")}>
      <div className={cn(className || "rounded-md border")}>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead
                      key={header.id}
                      className="h-auto min-h-10 whitespace-nowrap"
                    >
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() && "selected"}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell
                      key={cell.id}
                      className="whitespace-nowrap truncate max-w-[300px]"
                      title={String(cell.getValue())}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  No results.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex align-items justify-between flex-shrink-0">
        {pagination ? <DataTablePagination table={table} /> : <div />}
        {downloadAs && <DownloadAs downloadAs={downloadAs} />}
      </div>
    </div>
  );
};

export const DataTable = memo(DataTableInternal) as typeof DataTableInternal;
