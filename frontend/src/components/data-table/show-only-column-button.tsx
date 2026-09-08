/* Copyright 2026 Marimo. All rights reserved. */
"use no memo";

import type { Table } from "@tanstack/react-table";
import { ScanEyeIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/utils/cn";
import { applyShowOnlyColumns } from "./hooks/use-column-visibility";

export const SHOW_ONLY_COLUMN_LABEL = "Show only this column";

interface ShowOnlyColumnButtonProps<TData> {
  table: Table<TData>;
  columnIds: string[];
  disabled: boolean;
  className?: string;
  iconClassName?: string;
}

export function ShowOnlyColumnButton<TData>({
  table,
  columnIds,
  disabled,
  className,
  iconClassName = "h-3 w-3",
}: ShowOnlyColumnButtonProps<TData>) {
  return (
    <Tooltip content={SHOW_ONLY_COLUMN_LABEL} delayDuration={400}>
      <Button
        type="button"
        variant="text"
        size="icon"
        aria-label={SHOW_ONLY_COLUMN_LABEL}
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : 0}
        className={cn(
          "h-6 w-6 hover:bg-muted text-muted-foreground hover:text-primary",
          disabled && "opacity-50",
          className,
        )}
        onPointerDown={(event) => {
          event.stopPropagation();
        }}
        onClick={(event) => {
          event.preventDefault();
          event.stopPropagation();
          if (disabled) {
            return;
          }
          applyShowOnlyColumns(table, columnIds);
        }}
      >
        <ScanEyeIcon className={iconClassName} strokeWidth={2.5} />
      </Button>
    </Tooltip>
  );
}
