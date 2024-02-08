/* Copyright 2024 Marimo. All rights reserved. */
import { Column, sortingFns } from "@tanstack/react-table";
import {
  ChevronsUpDown,
  ArrowDownNarrowWideIcon,
  ArrowDownWideNarrowIcon,
  ArrowDown10Icon,
  ArrowDown01Icon,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { Button } from "@/components/ui/button";
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
    <div className={cn("group flex items-center space-x-2", className)}>
      <span className="flex-1">{header}</span>
      <DropdownMenu modal={false}>
        <DropdownMenuTrigger asChild={true}>
          <Button
            variant="ghost"
            size="xs"
            className={cn(
              "ml-3 h-5 data-[state=open]:bg-accent m-0 p-1",
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
          </Button>
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
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
};
