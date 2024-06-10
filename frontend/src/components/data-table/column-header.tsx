/* Copyright 2024 Marimo. All rights reserved. */
import { Column, sortingFns } from "@tanstack/react-table";
import {
  ChevronsUpDown,
  ArrowDownNarrowWideIcon,
  ArrowDownWideNarrowIcon,
  ArrowDown10Icon,
  ArrowDown01Icon,
  CopyIcon,
} from "lucide-react";

import { cn } from "@/utils/cn";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface DataTableColumnHeaderProps<TData, TValue>
  extends React.HTMLAttributes<HTMLDivElement> {
  column: Column<TData, TValue>;
  header: React.ReactNode;
}

export const DataTableColumnHeader = <TData, TValue>({
  column,
  header,
  className,
}: DataTableColumnHeaderProps<TData, TValue>) => {
  if (!column.getCanSort()) {
    return <div className={cn(className)}>{header}</div>;
  }

  const sortFn = column.getSortingFn();
  const AscIcon =
    sortFn === sortingFns.basic ? ArrowDown01Icon : ArrowDownNarrowWideIcon;
  const DescIcon =
    sortFn === sortingFns.basic ? ArrowDown10Icon : ArrowDownWideNarrowIcon;

  return (
    <DropdownMenu modal={false}>
      <DropdownMenuTrigger asChild={true}>
        <div
          className={cn(
            "group flex items-center my-1 space-between w-full select-none gap-2 border hover:border-border border-transparent hover:bg-[var(--slate-3)] data-[state=open]:bg-[var(--slate-3)] data-[state=open]:border-border rounded px-2 -mx-2",
            className,
          )}
          data-testid="data-table-sort-button"
        >
          <span className="flex-1">{header}</span>
          <span
            className={cn(
              "h-5 py-1 px-2 mr-2",
              !column.getIsSorted() &&
                "invisible group-hover:visible data-[state=open]:visible",
            )}
          >
            {column.getIsSorted() === "desc" ? (
              <DescIcon className="h-3 w-3" />
            ) : column.getIsSorted() === "asc" ? (
              <AscIcon className="h-3 w-3" />
            ) : (
              <ChevronsUpDown className="h-3 w-3" />
            )}
          </span>
        </div>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start">
        <DropdownMenuItem onClick={() => column.toggleSorting(false)}>
          <AscIcon className="mr-2 h-3.5 w-3.5 text-muted-foreground/70" />
          Asc
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => column.toggleSorting(true)}>
          <DescIcon className="mr-2 h-3.5 w-3.5 text-muted-foreground/70" />
          Desc
        </DropdownMenuItem>
        {column.getIsSorted() && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => column.clearSorting()}>
              <ChevronsUpDown className="mr-2 h-3.5 w-3.5 text-muted-foreground/70" />
              Clear
            </DropdownMenuItem>
          </>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={() => navigator.clipboard.writeText(column.id)}
        >
          <CopyIcon className="mr-2 h-3.5 w-3.5 text-muted-foreground/70" />
          Copy column name
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const DataTableColumnHeaderWithSummary = <TData, TValue>({
  column,
  header,
  summary,
  className,
}: DataTableColumnHeaderProps<TData, TValue> & {
  summary: React.ReactNode;
}) => {
  return (
    <div
      className={cn(
        "flex flex-col h-full py-1 justify-between items-start gap-1",
        className,
      )}
    >
      <DataTableColumnHeader
        column={column}
        header={header}
        className={className}
      />
      {summary}
    </div>
  );
};
