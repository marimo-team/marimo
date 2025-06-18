/* Copyright 2024 Marimo. All rights reserved. */

import type * as api from "@marimo-team/marimo-api";
import { MultiColumn } from "@/utils/id-tree";
import { Logger } from "@/utils/Logger";
import { parseOutline } from "../dom/outline";
import { CellId } from "./ids";
import {
  type CellData,
  type CellRuntimeState,
  createCellRuntimeState,
} from "./types";

// Constants
const DEFAULT_TIMESTAMP = 0;
const EMPTY_STRING = "";

type SessionCell = api.Session["NotebookSessionV1"]["cells"][0];
type NotebookCell = api.Notebook["NotebookV1"]["cells"][0];

interface ValidationResult {
  isValid: boolean;
  error?: string;
}

function validateSessionNotebookCompatibility(
  session: api.Session["NotebookSessionV1"] | null | undefined,
  notebook: api.Notebook["NotebookV1"] | null | undefined,
): ValidationResult {
  if (!session && !notebook) {
    return {
      isValid: false,
      error: "",
    };
  }

  if (!session || !notebook) {
    return { isValid: true }; // One is null, which is fine
  }

  return { isValid: true };
}

function createCellDataFromNotebook(
  cellId: CellId,
  notebookCell: NotebookCell,
): CellData {
  return {
    id: cellId,
    name: notebookCell.name ?? EMPTY_STRING,
    code: notebookCell.code ?? EMPTY_STRING,
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

function createCellRuntimeFromSession(
  sessionCell: SessionCell | null | undefined,
): CellRuntimeState {
  const runtimeState = createCellRuntimeState();

  if (!sessionCell) {
    return runtimeState;
  }

  // Handle outputs - prioritize by type and use first available
  const outputs = sessionCell.outputs || [];
  const primaryOutput =
    outputs.find((output) => output.type === "data") ||
    outputs.find((output) => output.type === "error") ||
    outputs[0];

  if (primaryOutput) {
    if (primaryOutput.type === "error") {
      runtimeState.output = {
        channel: "marimo-error",
        data: [
          {
            type: "unknown",
            msg: primaryOutput.evalue,
          },
        ],
        mimetype: "application/vnd.marimo+error",
        timestamp: DEFAULT_TIMESTAMP,
      };
    } else if (primaryOutput.type === "data") {
      const mimeType = Object.keys(primaryOutput.data)[0];
      const data = Object.values(primaryOutput.data)[0];
      runtimeState.output = {
        channel: "output",
        data: data as {},
        mimetype: mimeType as "application/json",
        timestamp: DEFAULT_TIMESTAMP,
      };
    }
  }

  const consoleOutputs = sessionCell.console || [];

  return {
    ...runtimeState,
    outline: runtimeState.output ? parseOutline(runtimeState.output) : null,
    consoleOutputs: consoleOutputs.map((consoleOutput) => ({
      channel: consoleOutput.name === "stderr" ? "stderr" : "stdout",
      data: consoleOutput.text,
      mimetype: "text/plain",
      timestamp: DEFAULT_TIMESTAMP,
    })),
  };
}

export function notebookStateFromSession(
  session: api.Session["NotebookSessionV1"] | null | undefined,
  notebook: api.Notebook["NotebookV1"] | null | undefined,
) {
  // Validate compatibility
  const validation = validateSessionNotebookCompatibility(session, notebook);
  if (!validation.isValid) {
    if (validation.error) {
      Logger.error(validation.error);
    }
    return null;
  }

  // Create lookup maps for efficient access
  // Replacing with the cellIds fallback.
  const sessionCellDataByHash = new Map(
    session?.cells.map((cell) => [cell.code_hash ?? cell.id, cell]),
  );

  const notebookCellDataByHash = new Map(
    notebook?.cells.map((cell) => [cell.code_hash ?? cell.id, cell]),
  );

  const cellData: Record<CellId, CellData> = {};
  const cellRuntime: Record<CellId, CellRuntimeState> = {};
  const cellIds: CellId[] = [];

  // Process each cell
  for (const [cellHash, notebookCell] of notebookCellDataByHash) {
    if (!cellHash) {
      continue;
    }

    const sessionCell = sessionCellDataByHash.get(cellHash);
    const cellId = (sessionCell?.id ?? CellId.create()) as CellId;
    cellIds.push(cellId);

    // Create cell data from notebook if available
    if (notebookCell) {
      cellData[cellId] = createCellDataFromNotebook(cellId, notebookCell);
    }

    // Create cell runtime
    // This needs always be created even if there is no session cell
    // in order to display the cell in the correct state
    cellRuntime[cellId] = createCellRuntimeFromSession(sessionCell);
  }

  if (cellIds.length === 0) {
    Logger.warn("Session and notebook must have at least one cell");
    return null;
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
