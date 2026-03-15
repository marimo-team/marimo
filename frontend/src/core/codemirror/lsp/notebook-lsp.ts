import type {
  LanguageServerClient,
  ProcessNotification,
} from "@open-rpc/client-js";
import type { ViewUpdate } from "@codemirror/view";
import { Logger } from "@/utils/Logger";
import { isUrl } from "@/utils/url";
import {
  getNotebookDocumentUri,
  getCellDocumentUri,
} from "./language-server";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { notebookAtom } from "@/core/cells/cells";
import { Filenames } from "@/core/constants";

const CELL_DOCUMENT_URI_PREFIX = "cell:///";

interface DiagnosticParams {
  uri: string;
  version?: number;
  diagnostics: Array<{
    range: {
      start: { line: number; character: number };
      end: { line: number; character: number };
    };
    message: string;
    severity?: number;
    source?: string;
  }>;
}

/**
 * Patches the processNotification to intercept publishDiagnostics
 * and convert notebook URIs to cell URIs.
 */
export function patchProcessNotification(
  client: LanguageServerClient,
  previousProcessNotification: ProcessNotification,
): ProcessNotification {
  return (notification) => {
    if (notification.method === "textDocument/publishDiagnostics") {
      const params = notification.params as DiagnosticParams;
      const notebookDocumentUri = getNotebookDocumentUri();

      // If the diagnostics are for the notebook document, we need to
      // split them up by cell.
      if (params.uri === notebookDocumentUri) {
        const { notebook } = store.get(notebookAtom);
        const cellIds = notebook.cellIds;

        // Group diagnostics by cell
        const diagnosticsByCell = new Map<CellId, DiagnosticParams>();
        for (const diagnostic of params.diagnostics) {
          const line = diagnostic.range.start.line;
          const cellId = getCellIdForLine(cellIds, line);
          if (cellId) {
            const cellDocumentUri = getCellDocumentUri(cellId);
            if (!diagnosticsByCell.has(cellId)) {
              diagnosticsByCell.set(cellId, {
                uri: cellDocumentUri,
                version: params.version,
                diagnostics: [],
              });
            }
            // Adjust the line numbers to be relative to the cell
            const cellStartLine = getCellStartLine(cellIds, cellId);
            const adjustedDiagnostic = {
              ...diagnostic,
              range: {
                start: {
                  line: diagnostic.range.start.line - cellStartLine,
                  character: diagnostic.range.start.character,
                },
                end: {
                  line: diagnostic.range.end.line - cellStartLine,
                  character: diagnostic.range.end.character,
                },
              },
            };
            diagnosticsByCell.get(cellId)!.diagnostics.push(adjustedDiagnostic);
          }
        }

        // Clear diagnostics for cells that are not in the current diagnostics
        const cellsToClear = new Set<string>();
        for (const cellId of cellIds) {
          const cellDocumentUri = getCellDocumentUri(cellId);
          if (!diagnosticsByCell.has(cellId)) {
            cellsToClear.add(cellDocumentUri);
          }
        }

        // Send diagnostics for each cell
        for (const [_cellId, cellParams] of diagnosticsByCell) {
          previousProcessNotification({
            method: "textDocument/publishDiagnostics",
            params: cellParams,
          });
        }

        // Clear diagnostics for cells that are not in the current diagnostics
        for (const cellDocumentUri of cellsToClear) {
          previousProcessNotification({
            method: "textDocument/publishDiagnostics",
            params: {
              uri: cellDocumentUri,
              version: params.version,
              diagnostics: [],
            },
          });
        }

        return;
      }
    }

    previousProcessNotification(notification);
  };
}

function getCellIdForLine(cellIds: CellId[], line: number): CellId | null {
  const { notebook } = store.get(notebookAtom);
  let currentLine = 0;
  for (const cellId of cellIds) {
    const cell = notebook.cellData[cellId];
    const cellLines = cell.code.split("\n").length;
    if (line < currentLine + cellLines) {
      return cellId;
    }
    currentLine += cellLines;
  }
  return null;
}

function getCellStartLine(cellIds: CellId[], cellId: CellId): number {
  const { notebook } = store.get(notebookAtom);
  let currentLine = 0;
  for (const id of cellIds) {
    if (id === cellId) {
      return currentLine;
    }
    const cell = notebook.cellData[id];
    currentLine += cell.code.split("\n").length;
  }
  return 0;
}

/**
 * Patches the didChange notification to convert cell URIs to notebook URIs.
 */
export function patchDidChangeNotification(
  params: {
    textDocument: { uri: string; version: number };
    contentChanges: Array<{ text: string }>;
  },
  getCellCode: (cellId: CellId) => string,
): {
  textDocument: { uri: string; version: number };
  contentChanges: Array<{ text: string }>;
} {
  const { uri } = params.textDocument;

  // If the URI is a cell URI, we need to convert it to a notebook URI
  if (uri.startsWith(CELL_DOCUMENT_URI_PREFIX)) {
    const notebookDocumentUri = getNotebookDocumentUri();
    const { notebook } = store.get(notebookAtom);
    const cellIds = notebook.cellIds;

    // Get the full notebook content
    const notebookContent = cellIds.map((id) => getCellCode(id)).join("\n");

    return {
      textDocument: {
        uri: notebookDocumentUri,
        version: params.textDocument.version,
      },
      contentChanges: [{ text: notebookContent }],
    };
  }

  return params;
}

/**
 * Patches the didOpen notification to convert cell URIs to notebook URIs.
 */
export function patchDidOpenNotification(params: {
  textDocument: {
    uri: string;
    languageId: string;
    version: number;
    text: string;
  };
}): {
  textDocument: {
    uri: string;
    languageId: string;
    version: number;
    text: string;
  };
} {
  const { uri } = params.textDocument;

  // If the URI is a cell URI, we need to convert it to a notebook URI
  if (uri.startsWith(CELL_DOCUMENT_URI_PREFIX)) {
    const notebookDocumentUri = getNotebookDocumentUri();
    const { notebook } = store.get(notebookAtom);
    const cellIds = notebook.cellIds;

    // Get the full notebook content
    const notebookContent = cellIds
      .map((id) => notebook.cellData[id].code)
      .join("\n");

    return {
      textDocument: {
        uri: notebookDocumentUri,
        languageId: params.textDocument.languageId,
        version: params.textDocument.version,
        text: notebookContent,
      },
    };
  }

  return params;
}

/**
 * Patches the didClose notification to convert cell URIs to notebook URIs.
 */
export function patchDidCloseNotification(params: {
  textDocument: { uri: string };
}): { textDocument: { uri: string } } | null {
  const { uri } = params.textDocument;

  // If the URI is a cell URI, we don't want to close the notebook document
  if (uri.startsWith(CELL_DOCUMENT_URI_PREFIX)) {
    return null;
  }

  return params;
}
