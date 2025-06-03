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

  // Only check they are equal if both are provided
  if (
    sessionCellIds.size > 0 &&
    notebookCellIds.size > 0 &&
    !Sets.equals(sessionCellIds, notebookCellIds)
  ) {
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
  // Prefer notebook cells (for ordering) over session cells if both are provided
  const initialPass = (notebook?.cells.map((cell) => cell.id) ??
    session?.cells.map((cell) => cell.id) ??
    []) as CellId[];
  // Replace nulls with basic ordinal values.
  // Since cell ids are pulled from strictly 'abc's, numerical values are bound
  // to be unique.
  let count = 0;
  return initialPass.map((id) => {
    if (id === null || id === undefined) {
      // pad to 4 chars
      return `${count++}`.padStart(4, "0") as CellId; // Generate a unique ID
    }
    return id;
  });
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

  // Get cell IDs
  const cellIds = getCellIds(session, notebook);
  if (cellIds.length === 0) {
    Logger.warn("Session and notebook must have at least one cell");
    return null;
  }

  // Create lookup maps for efficient access
  // Replacing with the cellIds fallback.
  const sessionCellData = new Map(
    cellIds.map((id, idx) => [id, session?.cells[idx]]),
  );

  const notebookCellData = new Map(
    cellIds.map((id, idx) => [id, notebook?.cells[idx]]),
  );

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

    // Create cell runtime
    // This needs always be created even if there is no session cell
    // in order to display the cell in the correct state
    cellRuntime[cellId] = createCellRuntimeFromSession(sessionCell);
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
