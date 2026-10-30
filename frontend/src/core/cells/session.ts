/* Copyright 2026 Marimo. All rights reserved. */

/** Read the notebook a page was served with: its cells as a host snapshot, and their outputs. */

import type * as Protocol from "@marimo-team/client/protocol";
import type * as api from "@marimo-team/marimo-api";
import { mergeArray } from "@/utils/edit-distance";
import { Logger } from "@/utils/Logger";
import { parseOutline } from "../dom/outline";
import type { StaticNotebookSnapshot } from "../transports/static";
import { CellId, SETUP_CELL_ID } from "./ids";
import { DEFAULT_CELL_NAME } from "./names";
import { type CellRuntimeState, createCellRuntimeState } from "./types";

/** The identity of a snapshot the page carries. A host's own stream replaces it. */
const EMBEDDED = "embedded";

// Constants
const DEFAULT_TIMESTAMP = 0;
const EMPTY_STRING = "";

type SessionCell = api.Session["NotebookSessionV1"]["cells"][0];
type NotebookCell = api.Notebook["NotebookV1"]["cells"][0];

/**
 * Get the cell ID from a cell object.
 * If the cell has an ID, use it.
 * If the cell has a name of "setup", use the special SETUP_CELL_ID.
 * Otherwise, generate a new random ID.
 */
function getCellId(cell: { id?: string | null; name?: string | null }): CellId {
  if (cell.id) {
    return cell.id as CellId;
  }
  if (cell.name === SETUP_CELL_ID) {
    return SETUP_CELL_ID;
  }
  return CellId.create();
}

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
    const cellIds = notebook?.cells.map((cell) => getCellId(cell)) || [];
    return {
      cellIds,
      sessionCellData: new Map(
        cellIds.map((id) => [id, null] as [CellId, SessionCell | null]),
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
    const cellIds = session.cells.map((cell) => getCellId(cell));
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
      // If the code hash is null, always return false, since reordering the
      // cells can get things out of sync, and creates a poor user experience.
      if (!sessionCodeHash) {
        return false;
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
      const id = getCellId(notebookCell);
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
      expand_output: false,
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

/** The cell as a host would describe it. A snapshot never changes, so its etags only need to be distinct. */
function cellRecord(cellId: CellId, cell: NotebookCell): Protocol.Cell {
  return {
    id: cellId,
    notebook_id: EMBEDDED,
    code: cell.code ?? EMPTY_STRING,
    name: cell.name || DEFAULT_CELL_NAME,
    config: {
      column: cell.config?.column ?? null,
      disabled: cell.config?.disabled ?? false,
      hide_code: cell.config?.hide_code ?? false,
      expand_output: cell.config?.expand_output ?? false,
    },
    etag: `${EMBEDDED}:${cellId}`,
    code_hash: cell.code_hash ?? `${EMBEDDED}:${cellId}:code`,
    version: 1,
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
            type: "exception",
            exception_type: primaryOutput.ename,
            msg: primaryOutput.evalue,
            raising_cell: null,
            traceback:
              primaryOutput.traceback.length === 0
                ? null
                : primaryOutput.traceback
                    .map((line, index, lines) =>
                      index < lines.length - 1 && !line.endsWith("\n")
                        ? `${line}\n`
                        : line,
                    )
                    .join(""),
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
    if (runtimeState.output && primaryOutput.code !== undefined) {
      runtimeState.output.code = primaryOutput.code;
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
          ...(consoleOutput.traceback_format === undefined
            ? {}
            : { traceback_format: consoleOutput.traceback_format }),
          timestamp: DEFAULT_TIMESTAMP,
          ...(consoleOutput.code === undefined
            ? {}
            : { code: consoleOutput.code }),
        };
      }
      // Handle StreamOutput (type: "stream")
      return {
        channel: consoleOutput.name === "stderr" ? "stderr" : "stdout",
        data: consoleOutput.text,
        mimetype: consoleOutput.mimetype ?? "text/plain",
        ...(consoleOutput.traceback_format === undefined
          ? {}
          : { traceback_format: consoleOutput.traceback_format }),
        timestamp: DEFAULT_TIMESTAMP,
        ...(consoleOutput.code === undefined
          ? {}
          : { code: consoleOutput.code }),
      };
    }),
  };
}

/**
 * Read the session and notebook a page embeds.
 *
 * The cells become a host snapshot the replica starts from, and the session's
 * outputs seed each cell's runtime until the kernel speaks. Null when the page
 * carries no cells.
 */
export function readExport({
  session,
  notebook,
  filename,
  appConfig,
}: {
  session: api.Session["NotebookSessionV1"] | null | undefined;
  notebook: api.Notebook["NotebookV1"] | null | undefined;
  filename: string | null;
  appConfig: Record<string, unknown>;
}): {
  snapshot: StaticNotebookSnapshot | null;
  cellRuntime: Record<CellId, CellRuntimeState>;
} {
  const { cellIds, sessionCellData, notebookCellData } =
    mergeSessionAndNotebookCells(session, notebook);
  if (cellIds.length === 0) {
    return { snapshot: null, cellRuntime: {} };
  }

  const cells: Protocol.Cell[] = [];
  const cellRuntime: Record<CellId, CellRuntimeState> = {};
  for (const cellId of cellIds) {
    cells.push(
      cellRecord(
        cellId,
        notebookCellData.get(cellId) ?? createEmptyNotebookCell(),
      ),
    );
    cellRuntime[cellId] = createCellRuntimeFromSession(
      sessionCellData.get(cellId),
    );
  }

  return {
    snapshot: {
      notebook: {
        id: EMBEDDED,
        project_id: EMBEDDED,
        path: filename,
        name: filename ?? EMPTY_STRING,
        updated_at: null,
      },
      document: {
        notebook_id: EMBEDDED,
        order: cellIds,
        app_config: appConfig,
        etag: `${EMBEDDED}:document`,
        saved_etag: `${EMBEDDED}:document`,
        order_etag: `${EMBEDDED}:order`,
        app_config_etag: `${EMBEDDED}:app_config`,
        version: 1,
      },
      cells,
    },
    cellRuntime,
  };
}
