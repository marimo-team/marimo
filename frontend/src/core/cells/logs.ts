/* Copyright 2023 Marimo. All rights reserved. */
import { CellMessage, OutputMessage } from "../kernel/messages";
import { CellId } from "./ids";

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

  return logs;
}
