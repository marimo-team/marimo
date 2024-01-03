/* Copyright 2023 Marimo. All rights reserved. */
import React from "react";
import { OutputMessage } from "@/core/kernel/messages";
import { formatOutput } from "../Output";
import { cn } from "@/utils/cn";
import { DEFAULT_CELL_NAME } from "@/core/cells/names";
import { NameCellContentEditable } from "../actions/name-cell-input";
import { CellId } from "@/core/cells/ids";

interface Props {
  cellId: CellId;
  cellName: string;
  consoleOutputs: OutputMessage[];
  stale: boolean;
}

export const ConsoleOutput = (props: Props): React.ReactNode => {
  const { consoleOutputs, stale, cellName, cellId } = props;
  const hasOutputs = consoleOutputs.length > 0;

  if (!hasOutputs && cellName === DEFAULT_CELL_NAME) {
    return null;
  }

  return (
    <div
      title={stale ? "This console output is stale" : undefined}
      className={cn(
        "console-output-area overflow-hidden rounded-b-lg",
        stale && "marimo-output-stale",
        hasOutputs ? "p-5" : "p-3"
      )}
    >
      {consoleOutputs.map((output) => formatOutput({ message: output }))}
      <NameCellContentEditable
        value={cellName}
        cellId={cellId}
        className="bg-[var(--slate-4)] border-[var(--slate-4)] hover:bg-[var(--slate-5)] dark:bg-[var(--sky-5)] dark:border-[var(--sky-5)] dark:bg-[var(--sky-6)] dark:text-[var(--sky-12)] text-[var(--slate-12)] rounded-tl rounded-br-lg absolute right-0 bottom-0 text-xs px-1.5 py-0.5 font-mono"
      />
    </div>
  );
};
