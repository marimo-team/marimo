/* Copyright 2024 Marimo. All rights reserved. */
import { MultiColumn } from "@/utils/id-tree";
import type * as api from "@marimo-team/marimo-api";
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
      error: "Both session and notebook are null/undefined",
    };
  }

  if (!session || !notebook) {
    return { isValid: true }; // One is null, which is fine
  }

  const sessionCellIds = new Set(session.cells.map((cell) => cell.id));
  const notebookCellIds = new Set(notebook.cells.map((cell) => cell.id));

  if (!Sets.equals(sessionCellIds, notebookCellIds)) {
    return {
      isValid: false,
      error:
        "Session and notebook must have the same cells if both are provided",
    };
  }

  return { isValid: true };
}

function getCellIds(
  session: api.Session["NotebookSessionV1"] | null | undefined,
  notebook: api.Notebook["NotebookV1"] | null | undefined,
): CellId[] {
  return (notebook?.cells.map((cell) => cell.id) ??
    session?.cells.map((cell) => cell.id) ??
    []) as CellId[];
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
  cellId: string,
  sessionCell: SessionCell,
): CellRuntimeState {
  const runtimeState = createCellRuntimeState();

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

  // Get cell IDs
  const cellIds = getCellIds(session, notebook);
  if (cellIds.length === 0) {
    Logger.warn("Session and notebook must have at least one cell");
    return null;
  }

  // Create lookup maps for efficient access
  const sessionCellData = session?.cells
    ? Maps.keyBy(session.cells, (cell) => cell.id)
    : new Map();
  const notebookCellData = notebook?.cells
    ? Maps.keyBy(notebook.cells, (cell) => cell.id)
    : new Map();

  const cellData: Record<CellId, CellData> = {};
  const cellRuntime: Record<CellId, CellRuntimeState> = {};

  // Process each cell
  for (const cellId of cellIds) {
    const sessionCell = sessionCellData.get(cellId);
    const notebookCell = notebookCellData.get(cellId);

    // Create cell data from notebook if available
    if (notebookCell) {
      cellData[cellId] = createCellDataFromNotebook(cellId, notebookCell);
    }

    // Create cell runtime from session if available
    if (sessionCell) {
      cellRuntime[cellId] = createCellRuntimeFromSession(cellId, sessionCell);
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
