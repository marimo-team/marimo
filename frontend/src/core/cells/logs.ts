/* Copyright 2024 Marimo. All rights reserved. */
import { CellMessage, OutputMessage } from "../kernel/messages";
import { CellId } from "./ids";
import { fromUnixTime } from "date-fns";

export interface CellLog {
  timestamp: number;
  level: "stdout" | "stderr";
  message: string;
  cellId: CellId;
}

export function getCellLogsForMessage(cell: CellMessage): CellLog[] {
  const logs: CellLog[] = [];
  const outputs: OutputMessage[] = [cell.console].filter(Boolean).flat();

  for (const output of outputs) {
    if (output.mimetype === "text/plain") {
      switch (output.channel) {
        case "stdout":
          logs.push({
            timestamp: output.timestamp,
            level: "stdout",
            message: output.data,
            cellId: cell.cell_id,
          });
          break;
        case "stderr":
        case "marimo-error":
          logs.push({
            timestamp: output.timestamp,
            level: "stderr",
            message: output.data,
            cellId: cell.cell_id,
          });
          break;
        default:
          break;
      }
    }
  }

  // Log each to the console
  logs.forEach(CellLogLogger.log);

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
