/* Copyright 2023 Marimo. All rights reserved. */
import { color } from "@codemirror/theme-one-dark";
import { Logger } from "vscode-languageserver-protocol";
import { CellMessage, OutputMessage } from "../kernel/messages";
import { CellId } from "./ids";
import { fromUnixTime } from "date-fns";

export interface CellLog {
  timestamp: number;
  level: "info" | "warning" | "error";
  message: string;
  cellId: CellId;
}

export function getCellLogsForMessage(cell: CellMessage): CellLog[] {
  const logs: CellLog[] = [];
  const outputs: OutputMessage[] = [cell.console].filter(Boolean).flat();

  for (const output of outputs) {
    if (output.mimetype === "text/plain") {
      switch (output.channel) {
        case "console":
        case "stdout":
          logs.push({
            timestamp: output.timestamp,
            level: "info",
            message: output.data,
            cellId: cell.cell_id,
          });
          break;
        case "stderr":
        case "marimo-error":
          logs.push({
            timestamp: output.timestamp,
            level: "error",
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
      payload.level === "info"
        ? "gray"
        : payload.level === "warning"
        ? "orange"
        : "red";
    let status = payload.level.toUpperCase();
    if (status === "WARNING") {
      status = "WARN";
    }
    console.log(
      `%c[${status}]`,
      `color:${color}; padding:2px 0; border-radius:2px; font-weight:bold`,
      `[${formatLogTimestamp(payload.timestamp)}]`,
      `(${payload.cellId}) ${payload.message}`
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
