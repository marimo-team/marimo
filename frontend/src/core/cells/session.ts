/* Copyright 2024 Marimo. All rights reserved. */

import type * as api from "@marimo-team/marimo-api";
import { mergeArray } from "@/utils/edit-distance";
import { MultiColumn } from "@/utils/id-tree";
import { Logger } from "@/utils/Logger";
import { parseOutline } from "../dom/outline";
import type { NotebookState } from "./cells";
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

function mergeSessionAndNotebookCells(
  session: api.Session["NotebookSessionV1"] | null | undefined,
  notebook: api.Notebook["NotebookV1"] | null | undefined,
): {
  cellIds: CellId[];
  sessionCellData: Map<CellId, SessionCell | null>;
  notebookCellData: Map<CellId, NotebookCell>;
} {
  const sessionCellData = new Map<CellId, SessionCell | null>();
  const notebookCellData = new Map<CellId, NotebookCell>();

  if (!session && !notebook) {
    return { cellIds: [], sessionCellData, notebookCellData };
  }

  if (!session) {
    const cellIds = (notebook?.cells.map(
      (cell) => cell.id ?? CellId.create(),
    ) || []) as CellId[];
    return {
      cellIds,
      sessionCellData: new Map(
        cellIds.map((id, idx) => [id, null] as [CellId, SessionCell | null]),
      ),
      notebookCellData: new Map(
        cellIds.map(
          (id, idx) =>
            [id, notebook?.cells[idx] || createEmptyNotebookCell()] as [
              CellId,
              NotebookCell,
            ],
        ),
      ),
    };
  }

  if (!notebook) {
    const cellIds = session.cells.map(
      (cell) => cell.id ?? CellId.create(),
    ) as CellId[];
    return {
      cellIds,
      sessionCellData: new Map(
        cellIds.map(
          (id, idx) => [id, session.cells[idx]] as [CellId, SessionCell | null],
        ),
      ),
      notebookCellData: new Map(
        cellIds.map(
          (id) => [id, createEmptyNotebookCell()] as [CellId, NotebookCell],
        ),
      ),
    };
  }

  // Both session and notebook exist - merge using edit distance on cell content
  // hash.
  const { merged: mergedSessionCells, edits } = mergeArray(
    session.cells,
    notebook.cells,
    (sessionCell, notebookCell) => {
      const sessionCodeHash = sessionCell.code_hash;
      // If the code hash is null, default to comparing ids
      if (!sessionCodeHash) {
        return sessionCell.id === notebookCell.id;
      }
      // Compare session cell code_hash with notebook cell code
      const notebookCodeHash = notebookCell.code_hash;
      return notebookCodeHash === sessionCodeHash;
    },
    // stub cell is empty session cell
    createEmptySessionCell(),
  );
  if (edits.distance > 0) {
    Logger.warn("Session and notebook have different cells, attempted merge.");
  }

  // Create merged cell arrays
  const mergedCellIdsTyped: CellId[] = [];

  // Defer to the notebook cells for the correct ordering.
  for (let i = 0; i < notebook.cells.length; i++) {
    const notebookCell = notebook.cells[i];
    if (notebookCell) {
      const id = (notebookCell.id ?? CellId.create()) as CellId;
      mergedCellIdsTyped.push(id);

      // Should always be set, but good typing fallback too.
      const sessionItem = mergedSessionCells[i] || createEmptySessionCell();
      sessionItem.id = id; // Ensure session cell has the correct ID

      sessionCellData.set(id, sessionItem);
      notebookCellData.set(id, notebookCell);
    } else {
      // This shouldn't happen since notebook cells are canonical
      Logger.warn("Merged notebook cell is null at index", i);
    }
  }

  return {
    cellIds: mergedCellIdsTyped,
    sessionCellData,
    notebookCellData,
  };
}

function createEmptyNotebookCell(): NotebookCell {
  return {
    id: CellId.create(),
    name: EMPTY_STRING,
    code: EMPTY_STRING,
    code_hash: null,
    config: {
      column: null,
      disabled: false,
      hide_code: false,
    },
  };
}

function createEmptySessionCell(): SessionCell {
  return {
    id: CellId.create(),
    code_hash: null,
    console: [],
    outputs: [],
  };
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
    consoleOutputs: consoleOutputs.map((consoleOutput) => {
      // Handle StreamMediaOutput (type: "streamMedia")
      if (consoleOutput.type === "streamMedia") {
        return {
          channel: "media",
          data: consoleOutput.data,
          mimetype: consoleOutput.mimetype,
          timestamp: DEFAULT_TIMESTAMP,
        };
      }
      // Handle StreamOutput (type: "stream")
      return {
        channel: consoleOutput.name === "stderr" ? "stderr" : "stdout",
        data: consoleOutput.text,
        mimetype: "text/plain",
        timestamp: DEFAULT_TIMESTAMP,
      };
    }),
  };
}

export function notebookStateFromSession(
  session: api.Session["NotebookSessionV1"] | null | undefined,
  notebook: api.Notebook["NotebookV1"] | null | undefined,
): NotebookState | null {
  // Merge session and notebook cells using edit distance
  const { cellIds, sessionCellData, notebookCellData } =
    mergeSessionAndNotebookCells(session, notebook);

  if (cellIds.length === 0) {
    Logger.warn("Session and notebook must have at least one cell");
    return null;
  }

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
    untouchedNewCells: new Set(),
  };
}
