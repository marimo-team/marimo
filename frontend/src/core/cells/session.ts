/* Copyright 2024 Marimo. All rights reserved. */
import { MultiColumn } from "@/utils/id-tree";
import type { INotebook, ISession } from "@marimo-team/marimo-api";
import { parseOutline } from "../dom/outline";
import type { CellId } from "./ids";
import {
  type CellData,
  type CellRuntimeState,
  createCellRuntimeState,
} from "./types";
import { Logger } from "@/utils/Logger";
import { Maps } from "@/utils/maps";
import { Sets } from "@/utils/sets";

export function notebookStateFromSession(
  session: ISession["NotebookSessionV1"] | null | undefined,
  notebook: INotebook["NotebookV1"] | null | undefined,
) {
  if (!session && !notebook) {
    return null;
  }
  const sessionCellIds = session?.cells.map((cell) => cell.id);
  const notebookCellIds = notebook?.cells.map((cell) => cell.id);

  if (
    session &&
    notebook &&
    !Sets.equals(new Set(sessionCellIds), new Set(notebookCellIds))
  ) {
    Logger.error(
      "Session and notebook must have the same cells if both are provided",
    );
    return null;
  }

  const cellIds = notebookCellIds ?? sessionCellIds ?? [];
  if (cellIds.length === 0) {
    Logger.warn("Session and notebook must have at least one cell");
    return null;
  }

  const cellData: Record<CellId, CellData> = {};
  const cellRuntime: Record<CellId, CellRuntimeState> = {};

  const sessionCellData = session?.cells
    ? Maps.keyBy(session.cells, (cell) => cell.id)
    : new Map();
  const notebookCellData = notebook?.cells
    ? Maps.keyBy(notebook.cells, (cell) => cell.id)
    : new Map();

  for (const cellId of cellIds) {
    const sessionCell = sessionCellData.get(cellId);
    const notebookCell = notebookCellData.get(cellId);

    if (notebookCell) {
      cellData[cellId] = {
        id: cellId,
        name: notebookCell.name ?? "",
        code: notebookCell.code ?? "",
        edited: false,
        lastCodeRun: null,
        lastExecutionTime: null,
        config: {
          column: notebookCell.config?.column ?? null,
          disabled: notebookCell.config?.disabled ?? false,
          hide_code: notebookCell.config?.hide_code ?? false,
        },
        serializedEditorState: null,
      };
    }

    if (sessionCell) {
      const output = sessionCell?.outputs[0];
      const consoleOutputs = sessionCell?.console ?? [];
      const runtimeState = createCellRuntimeState();

      if (output) {
        if (output.type === "error") {
          runtimeState.output = {
            channel: "marimo-error",
            data: [
              {
                type: "unknown",
                msg: output.evalue,
              },
            ],
            mimetype: "application/vnd.marimo+error",
            timestamp: 0,
          };
        } else if (output.type === "data") {
          const mimeType = Object.keys(output.data)[0];
          const data = Object.values(output.data)[0];
          runtimeState.output = {
            channel: "output",
            data: data as {},
            mimetype: mimeType as "application/json",
            timestamp: 0,
          };
        }
      }

      cellRuntime[cellId] = {
        ...runtimeState,
        outline: output ? parseOutline(runtimeState.output) : null,
        consoleOutputs: consoleOutputs.map((consoleOutput) => ({
          channel: consoleOutput.name === "stderr" ? "stderr" : "stdout",
          data: consoleOutput.text,
          mimetype: "text/plain",
          timestamp: 0,
        })),
      };
    }
  }

  return {
    cellIds: MultiColumn.from([cellIds]),
    cellData: cellData,
    cellRuntime: cellRuntime,
    cellHandles: {},
    history: [],
    scrollKey: null,
    cellLogs: [],
  };
}
