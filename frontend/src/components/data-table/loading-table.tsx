/* Copyright 2024 Marimo. All rights reserved. */
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/utils/cn";

interface Props {
  wrapperClassName?: string;
  className?: string;
  pageSize?: number;
}

export const LoadingTable = ({
  wrapperClassName,
  className,
  pageSize = 10,
}: Props) => {
  const NUM_COLUMNS = 8;

  return (
    <div className={cn(wrapperClassName, "flex flex-col space-y-2")}>
      <div className={cn(className || "rounded-md border")}>
        <Table>
          <TableHeader>
            {Array.from({ length: 1 }).map((_, i) => (
              <TableRow key={i}>
                {Array.from({ length: NUM_COLUMNS }).map((_, j) => (
                  <TableHead key={j}>
                    <div className="h-4 bg-[var(--slate-5)] animate-pulse rounded-md w-[70%]" />
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {Array.from({ length: pageSize }).map((_, i) => (
              <TableRow key={i}>
                {Array.from({ length: NUM_COLUMNS }).map((_, j) => (
                  <TableCell key={j}>
                    <div className="h-4 bg-[var(--slate-5)] animate-pulse rounded-md w-[90%]" />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="flex align-items justify-between flex-shrink-0 h-8" />
    </div>
  );
};
