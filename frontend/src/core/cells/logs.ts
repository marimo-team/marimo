/* Copyright 2024 Marimo. All rights reserved. */

import { fromUnixTime } from "date-fns";
import { toast } from "@/components/ui/use-toast";
import { invariant } from "@/utils/invariant";
import type { CellMessage, OutputMessage } from "../kernel/messages";
import { isErrorMime } from "../mime";
import type { CellId } from "./ids";

export interface CellLog {
  timestamp: number;
  level: "stdout" | "stderr";
  message: string;
  cellId: CellId;
}

let didAlreadyToastError = false;

export function getCellLogsForMessage(cell: CellMessage): CellLog[] {
  const logs: CellLog[] = [];
  const consoleOutputs: OutputMessage[] = [cell.console].filter(Boolean).flat();

  for (const output of consoleOutputs) {
    if (output.mimetype === "text/plain") {
      invariant(typeof output.data === "string", "expected string");
      const isError =
        output.channel === "stderr" || output.channel === "marimo-error";
      switch (output.channel) {
        case "stdout":
        case "stderr":
        case "marimo-error":
          logs.push({
            timestamp: output.timestamp || Date.now(),
            level: isError ? "stderr" : "stdout",
            message: output.data,
            cellId: cell.cell_id as CellId,
          });
          break;
        default:
          break;
      }
    }
  }

  // Log each to the console
  logs.forEach(CellLogLogger.log);

  // If there is no console output, but there is an error output, let's log that instead
  // This happens in run mode when stderr is not sent to the client.
  if (
    consoleOutputs.length === 0 &&
    isErrorMime(cell.output?.mimetype) &&
    Array.isArray(cell.output.data)
  ) {
    cell.output.data.forEach((error) => {
      CellLogLogger.log({
        level: "stderr",
        cellId: cell.cell_id as CellId,
        timestamp: cell.timestamp,
        message: JSON.stringify(error),
      });
    });

    const shouldToast = cell.output.data.some(
      (error) => error.type === "internal",
    );
    if (!didAlreadyToastError && shouldToast) {
      didAlreadyToastError = true;
      toast({
        title: "An internal error occurred",
        description: "See console for details.",
        className:
          "text-xs text-background bg-[var(--red-10)] py-2 pl-3 [&>*]:flex [&>*]:gap-3",
      });
    }
  }

  return logs;
}

const CellLogLogger = {
  log: (payload: CellLog) => {
    const color =
      payload.level === "stdout"
        ? "gray"
        : payload.level === "stderr"
          ? "red"
          : "orange";
    const status = payload.level.toUpperCase();
    // eslint-disable-next-line no-console
    console.log(
      `%c[${status}]`,
      `color:${color}; padding:2px 0; border-radius:2px; font-weight:bold`,
      `[${formatLogTimestamp(payload.timestamp)}]`,
      `(${payload.cellId}) ${payload.message}`,
    );
  },
};

// e.g. 9:45:10 AM
export function formatLogTimestamp(timestamp: number): string {
  try {
    // parse from UTC
    const date = fromUnixTime(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour12: true,
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
    });
  } catch {
    return "";
  }
}
