/* Copyright 2026 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import type * as LSP from "vscode-languageserver-protocol";
import { getNotebook } from "@/core/cells/cells";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";
import { Objects } from "@/utils/objects";
import { getPositionAtWordBounds } from "../completion/hints";
import { topologicalCodesAtom } from "../copilot/getCodes";
import {
  getEditorCodeAsPython,
  updateEditorCodeFromPython,
} from "../language/utils";
import { createNotebookLens, type NotebookLens } from "./lens";
import { normalizeLspDocumentation } from "./normalize-markdown-math";
import {
  CellDocumentUri,
  type ILanguageServerClient,
  isClientWithNotify,
} from "./types";
import { getLSPDocument } from "./utils";

/**
 * Check if a variable name is private (starts with underscore but not dunder).
 * Private variables in marimo are cell-local and should not be renamed across cells.
 */
function isPrivateVariable(name: string): boolean {
  return name.startsWith("_") && !name.startsWith("__");
}

class Snapshotter {
  private documentVersion = 0;
  private readonly getNotebookCode: () => {
    cellIds: CellId[];
    codes: Record<CellId, string>;
  };

  constructor(
    getNotebookCode: () => {
      cellIds: CellId[];
      codes: Record<CellId, string>;
    },
  ) {
    this.getNotebookCode = getNotebookCode;
  }

  private lastSnapshot: NotebookLens | null = null;

  public snapshot() {
    const lens = this.getLens();
    const didChange = this.lastSnapshot?.mergedText !== lens.mergedText;
    if (!didChange) {
      return {
        lens,
        didChange,
        version: this.documentVersion,
      };
    }

    // Increment the version and update the snapshot
    this.documentVersion++;
    this.lastSnapshot = lens;

    return {
      lens,
      didChange,
      version: this.documentVersion,
    };
  }

  public getLatestSnapshot() {
    if (!this.lastSnapshot) {
      throw new Error("No snapshots");
    }
    return { lens: this.lastSnapshot, version: this.documentVersion };
  }

  private getLens() {
    const { cellIds, codes } = this.getNotebookCode();
    return createNotebookLens(cellIds, codes);
  }
}

const defaultGetNotebookEditors = () => {
  const evs = getNotebook().cellHandles;
  return Objects.mapValues(evs, (r) => r.current?.editorViewOrNull);
};

function normalizeTextDocumentation(
  documentation: string | LSP.MarkupContent | undefined,
): string | LSP.MarkupContent | undefined {
  const normalized = normalizeLspDocumentation(
    documentation as LSP.MarkupContent | LSP.MarkedString | undefined,
  );
  if (Array.isArray(normalized)) {
    return documentation;
  }
  return normalized as string | LSP.MarkupContent | undefined;
}

function normalizeCompletionItem(item: LSP.CompletionItem): LSP.CompletionItem {
  return {
    ...item,
    documentation: normalizeTextDocumentation(item.documentation),
  };
}

function normalizeCompletionResponse(
  response: LSP.CompletionList | LSP.CompletionItem[] | null,
): LSP.CompletionList | LSP.CompletionItem[] | null {
  if (response == null) {
    return null;
  }
  if (Array.isArray(response)) {
    return response.map((item) => normalizeCompletionItem(item));
  }
  return {
    ...response,
    items: response.items.map((item) => normalizeCompletionItem(item)),
  };
}

function normalizeSignatureHelpResponse(
  response: LSP.SignatureHelp,
): LSP.SignatureHelp {
  return {
    ...response,
    signatures: response.signatures.map((signature) => ({
      ...signature,
      documentation: normalizeTextDocumentation(signature.documentation),
      parameters: signature.parameters?.map((parameter) => ({
        ...parameter,
        documentation: normalizeTextDocumentation(parameter.documentation),
      })),
    })),
  };
}

export class NotebookLanguageServerClient implements ILanguageServerClient {
  public readonly documentUri: LSP.DocumentUri;
  private readonly client: ILanguageServerClient;
  private readonly snapshotter: Snapshotter;
  private readonly getNotebookEditors: () => Record<
    CellId,
    EditorView | null | undefined
  >;
  private readonly initialSettings: Record<string, unknown>;
  /**
   * Tracks which cell document URIs have been opened with the LSP server.
   * Used to clear diagnostics for cells that no longer have any.
   *
   * This set is pruned when diagnostics are processed to only include
   * cells that exist in the current notebook snapshot.
   */
  private static readonly SEEN_CELL_DOCUMENT_URIS = new Set<CellDocumentUri>();

  /**
   * Remove cell URIs that are no longer in the notebook.
   * Called during diagnostic processing to prevent memory leaks.
   */
  private static pruneSeenCellUris(currentCellIds: Set<CellId>): void {
    for (const uri of NotebookLanguageServerClient.SEEN_CELL_DOCUMENT_URIS) {
      const cellId = CellDocumentUri.parse(uri);
      if (!currentCellIds.has(cellId)) {
        NotebookLanguageServerClient.SEEN_CELL_DOCUMENT_URIS.delete(uri);
      }
    }
  }

  /**
   * Cache of completion items to avoid jitter while typing in the same completion item
   */
  private readonly completionItemCache = new LRUCache<
    string,
    Promise<LSP.CompletionItem>
  >(10);

  constructor(
    client: ILanguageServerClient,
    initialSettings: Record<string, unknown>,
    getNotebookEditors: () => Record<
      CellId,
      EditorView | null | undefined
    > = defaultGetNotebookEditors,
  ) {
    this.documentUri = getLSPDocument();
    this.getNotebookEditors = getNotebookEditors;
    this.initialSettings = initialSettings;
    this.client = client;
    this.patchProcessNotification();

    // Handle configuration after initialization
    this.initializePromise.then(() => {
      invariant(
        isClientWithNotify(this.client),
        "notify is not a method on the client",
      );
      this.client.notify("workspace/didChangeConfiguration", {
        settings: initialSettings,
      });
    });

    this.snapshotter = new Snapshotter(this.getNotebookCode.bind(this));
  }

  onNotification(
    listener: (n: {
      jsonrpc: "2.0";
      id?: null | undefined;
      method: "textDocument/publishDiagnostics";
      params: LSP.PublishDiagnosticsParams;
    }) => void,
  ): () => boolean {
    return this.client.onNotification(listener);
  }

  get ready(): boolean {
    return this.client.ready;
  }

  set ready(value: boolean) {
    this.client.ready = value;
  }

  get capabilities(): LSP.ServerCapabilities | null {
    return this.client.capabilities;
  }

  set capabilities(value: LSP.ServerCapabilities) {
    this.client.capabilities = value;
  }

  get initializePromise(): Promise<void> {
    return this.client.initializePromise;
  }

  set initializePromise(value: Promise<void>) {
    this.client.initializePromise = value;
  }

  get clientCapabilities() {
    return this.client.clientCapabilities;
  }

  async initialize(): Promise<void> {
    await this.client.initialize();
  }

  close(): void {
    this.client.close();
  }

  /**
   * Re-synchronize all open documents with the LSP server.
   * This is called after a WebSocket reconnection to restore document state.
   */
  public async resyncAllDocuments(): Promise<void> {
    invariant(
      isClientWithNotify(this.client),
      "notify is not a method on the client",
    );
    await this.client.initialize();
    this.client.notify("workspace/didChangeConfiguration", {
      settings: this.initialSettings,
    });

    // Get the current document state
    const { lens, version } = this.snapshotter.snapshot();

    // Re-open the merged document with the LSP server
    // This sends a textDocument/didOpen for the entire notebook
    await this.client.textDocumentDidOpen({
      textDocument: {
        languageId: "python", // Default to Python for marimo notebooks
        text: lens.mergedText,
        uri: this.documentUri,
        version: version,
      },
    });

    Logger.log("[lsp] Document re-synchronization complete");
  }

  private getNotebookCode() {
    return store.get(topologicalCodesAtom);
  }

  private assertCellDocumentUri(
    uri: LSP.DocumentUri,
  ): asserts uri is CellDocumentUri {
    invariant(CellDocumentUri.is(uri), "Execpted URI to be CellDocumentUri");
  }

  /**
   * Example of "zoom in" for textDocumentDidOpen, so server sees a merged doc.
   */
  public async textDocumentDidOpen(params: LSP.DidOpenTextDocumentParams) {
    Logger.debug("[lsp] textDocumentDidOpen", params);
    const cellDocumentUri = params.textDocument.uri;
    this.assertCellDocumentUri(cellDocumentUri);

    const { lens, version } = this.snapshotter.snapshot();

    NotebookLanguageServerClient.SEEN_CELL_DOCUMENT_URIS.add(cellDocumentUri);

    // Pass merged doc to LSP
    const result = await this.client.textDocumentDidOpen({
      textDocument: {
        languageId: params.textDocument.languageId,
        text: lens.mergedText,
        uri: this.documentUri,
        version: version,
      },
    });

    if (!result) {
      return params;
    }

    return {
      ...result,
      textDocument: {
        ...result.textDocument,
        text: lens.mergedText,
      },
    };
  }

  /**
   * Synchronize the document with the LSP server and return the lens used.
   * This ensures the caller uses the same lens that was sent to the server,
   * avoiding race conditions if cells change between sync and subsequent operations.
   */
  async sync(): Promise<{
    params: LSP.DidChangeTextDocumentParams;
    lens: NotebookLens;
  }> {
    const { lens, version, didChange } = this.snapshotter.snapshot();
    const params: LSP.DidChangeTextDocumentParams = {
      textDocument: {
        uri: this.documentUri,
        version: version,
      },
      contentChanges: [{ text: lens.mergedText }],
    };

    if (didChange) {
      // Update changes for merged doc
      await this.client.textDocumentDidChange(params);
    }

    return { params, lens };
  }

  public async textDocumentDidChange(params: LSP.DidChangeTextDocumentParams) {
    Logger.debug("[lsp] textDocumentDidChange", params);
    // We know how to only handle single content changes
    // But that is all we expect to receive
    if (params.contentChanges.length === 1) {
      const { params: syncParams } = await this.sync();
      return syncParams;
    }

    Logger.warn("[lsp] Unhandled textDocumentDidChange", params);

    return this.client.textDocumentDidChange(params);
  }

  async textDocumentDefinition(
    params: LSP.DefinitionParams,
  ): Promise<LSP.Definition | LSP.LocationLink[] | null> {
    // Get the cell document URI from the params
    const cellDocumentUri = params.textDocument.uri;
    if (!CellDocumentUri.is(cellDocumentUri)) {
      Logger.warn("Invalid cell document URI", cellDocumentUri);
      return null;
    }

    // Sync and use the same lens that was sent to the server
    const { lens } = await this.sync();

    // Find the lens for this cell
    const cellId = CellDocumentUri.parse(cellDocumentUri);

    return this.client.textDocumentDefinition({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      // Transform the position to the cell coordinates
      position: lens.transformPosition(params.position, cellId),
    });
  }

  async textDocumentSignatureHelp(
    params: LSP.SignatureHelpParams,
  ): Promise<LSP.SignatureHelp | null> {
    const cellDocumentUri = params.textDocument.uri;
    if (!CellDocumentUri.is(cellDocumentUri)) {
      Logger.warn("Invalid cell document URI", cellDocumentUri);
      return null;
    }

    // Sync and use the same lens that was sent to the server
    const { lens } = await this.sync();

    const cellId = CellDocumentUri.parse(cellDocumentUri);

    const response = await this.client.textDocumentSignatureHelp({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      // Transform the position to the cell coordinates
      position: lens.transformPosition(params.position, cellId),
    });

    if (!response) {
      return null;
    }

    return normalizeSignatureHelpResponse(response);
  }

  /**
   * Code actions are currently disabled because mapping code action edits
   * back to individual cells is complex and error-prone.
   *
   * The LSP server returns edits in merged document coordinates, but we need
   * to apply them to individual cell editors. Unlike simple position transforms
   * (hover, completion), code actions can include arbitrary text edits that
   * may span multiple cells or change line counts, making the reverse mapping
   * unreliable.
   *
   * To enable this, we would need to:
   * 1. Transform edit ranges from merged doc coordinates to cell coordinates
   * 2. Handle edits that span cell boundaries (split or reject them)
   * 3. Apply edits atomically across multiple cell editors
   *
   * See textDocumentRename for a similar workaround that manually applies edits.
   */
  textDocumentCodeAction(
    params: LSP.CodeActionParams,
  ): Promise<(LSP.Command | LSP.CodeAction)[] | null> {
    const disabledCodeAction = true;
    if (disabledCodeAction) {
      return Promise.resolve(null);
    }
    return this.client.textDocumentCodeAction(params);
  }

  /**
   * Rename implementation with manual edit application.
   *
   * This is a workaround because the standard LSP rename flow doesn't work well
   * with our notebook architecture. The LSP server returns a WorkspaceEdit with
   * edits in merged document coordinates, but CodeMirror's LSP plugin expects
   * edits for individual cell documents.
   *
   * Instead of trying to transform the WorkspaceEdit (which is complex because
   * edits can span cells, change line counts, etc.), we:
   * 1. Request the rename from the LSP server
   * 2. Extract the new merged text from the response
   * 3. Split it back into per-cell text using the lens
   * 4. Manually update each cell's editor
   *
   * This approach is simpler and more reliable, though it bypasses the normal
   * LSP edit application flow. The trade-off is that we lose undo grouping
   * across cells.
   */
  async textDocumentRename(
    params: LSP.RenameParams,
  ): Promise<LSP.WorkspaceEdit | null> {
    // Get the cell document URI from the params
    const cellDocumentUri = params.textDocument.uri;
    if (!CellDocumentUri.is(cellDocumentUri)) {
      Logger.warn("Invalid cell document URI", cellDocumentUri);
      return null;
    }

    const cellId = CellDocumentUri.parse(cellDocumentUri);

    // Sync and use the same lens that was sent to the server
    const { lens } = await this.sync();

    const transformedPosition = lens.transformPosition(params.position, cellId);

    // Request
    const response = await this.client.textDocumentRename({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: transformedPosition,
    });

    if (!response) {
      return null;
    }

    // Get all the edits from the response
    const edits = response.documentChanges?.flatMap((change) => {
      if ("edits" in change) {
        return change.edits;
      }
      return [];
    });

    // Validate its a single edit
    if (!edits || edits.length !== 1) {
      Logger.warn("Expected exactly one edit", edits);
      return response;
    }

    const edit = edits[0];
    if (!("newText" in edit)) {
      Logger.warn("Expected newText in edit", edit);
      return response;
    }

    // Get the new text for all the cells (some may be unchanged)
    const newEdits = lens.getEditsForNewText(edit.newText);
    const editsToNewCode = new Map(newEdits.map((e) => [e.cellId, e.text]));

    // Update the code in the plugins manually
    const editors = this.getNotebookEditors();

    // Check if this is a private variable rename (should only affect current cell)
    // Private variables in marimo are cell-local and should not be renamed across cells
    const originEditor = editors[cellId];
    let isPrivateRename = false;
    if (originEditor) {
      // Convert LSP position (line, character) to CodeMirror position
      const line = originEditor.state.doc.line(params.position.line + 1);
      const cmPosition = line.from + params.position.character;
      const { startToken, endToken } = getPositionAtWordBounds(
        originEditor.state.doc,
        cmPosition,
      );
      const originalName = originEditor.state.doc.sliceString(
        startToken,
        endToken,
      );
      isPrivateRename = isPrivateVariable(originalName);
      if (isPrivateRename) {
        Logger.debug(
          "[lsp] Private variable rename detected, limiting to current cell",
          originalName,
        );
      }
    }

    const failedCells: CellId[] = [];
    let updatedCount = 0;

    for (const [currentCellId, ev] of Objects.entries(editors)) {
      // For private variable renames, only update the originating cell
      if (isPrivateRename && currentCellId !== cellId) {
        continue;
      }

      const newCode = editsToNewCode.get(currentCellId);
      if (newCode == null) {
        Logger.warn("[lsp] No new code for cell during rename", currentCellId);
        failedCells.push(currentCellId);
        continue;
      }

      if (!ev) {
        Logger.warn(
          "[lsp] No editor view for cell during rename",
          currentCellId,
        );
        failedCells.push(currentCellId);
        continue;
      }

      // Only update if it has changed
      const code = getEditorCodeAsPython(ev);
      if (code !== newCode) {
        updateEditorCodeFromPython(ev, newCode);
        updatedCount++;
      }
    }

    if (failedCells.length > 0) {
      Logger.error(
        `[lsp] Rename partially failed: could not update ${failedCells.length} cell(s)`,
        failedCells,
      );
    }

    Logger.debug(`[lsp] Rename completed: updated ${updatedCount} cell(s)`);

    return {
      ...response,
      documentChanges: [
        {
          edits: [],
          textDocument: {
            uri: cellDocumentUri,
            version: 0,
          },
        },
      ],
    };
  }

  async completionItemResolve(
    params: LSP.CompletionItem,
  ): Promise<LSP.CompletionItem> {
    // Used cached result to avoid jitter while typing in the same completion item
    const key = JSON.stringify(params);
    const cached = this.completionItemCache.get(key);
    if (cached) {
      return cached;
    }

    const resolved = this.client
      .completionItemResolve(params)
      .then((item) => normalizeCompletionItem(item));
    this.completionItemCache.set(key, resolved);
    return resolved;
  }

  async textDocumentPrepareRename(
    params: LSP.PrepareRenameParams,
  ): Promise<LSP.PrepareRenameResult | null> {
    // Get the cell document URI from the params
    const cellDocumentUri = params.textDocument.uri;
    if (!CellDocumentUri.is(cellDocumentUri)) {
      Logger.warn("Invalid cell document URI", cellDocumentUri);
      return null;
    }

    // Sync and use the same lens that was sent to the server
    const { lens } = await this.sync();

    const cellId = CellDocumentUri.parse(cellDocumentUri);

    return this.client.textDocumentPrepareRename({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: lens.transformPosition(params.position, cellId),
    });
  }

  public async textDocumentHover(params: LSP.HoverParams) {
    Logger.debug("[lsp] textDocumentHover", params);

    // Sync and use the same lens that was sent to the server
    const { lens } = await this.sync();

    const cellId = CellDocumentUri.parse(params.textDocument.uri);

    const hover = await this.client.textDocumentHover({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: lens.transformPosition(params.position, cellId),
    });

    if (!hover) {
      Logger.debug("[lsp] no hover result");
      return hover;
    }

    // Change content kind to markdown and wrap in our classnames
    if (typeof hover.contents === "object" && "kind" in hover.contents) {
      hover.contents = {
        kind: "markdown",
        value: hover.contents.value,
      };
    }
    hover.contents =
      normalizeLspDocumentation(hover.contents) ?? hover.contents;

    // Empty
    if (hover.contents === "") {
      // Handled downstream, but the types are off
      return null as unknown as LSP.Hover;
    }

    // Convert ranges back to cell coordinates
    if (hover.range) {
      hover.range = lens.reverseRange(hover.range, cellId);
    }
    return hover;
  }

  public async textDocumentCompletion(params: LSP.CompletionParams) {
    const { lens } = this.snapshotter.getLatestSnapshot();

    // Check if URI is valid
    if (!CellDocumentUri.is(params.textDocument.uri)) {
      Logger.error(
        "[lsp] Invalid cell document URI in completion request",
        params.textDocument.uri,
      );
      return null;
    }

    const cellId = CellDocumentUri.parse(params.textDocument.uri);

    // Check if cellId is valid (not undefined string)
    if (!cellId || cellId === "undefined") {
      Logger.error("[lsp] Invalid cellId 'undefined' in completion request", {
        cellId,
        uri: params.textDocument.uri,
        availableCellIds: lens.cellIds,
      });
      // Return null to fail gracefully instead of sending wrong position
      return null;
    }

    // Warn if cellId not found in lens (might be okay if cell was just added)
    if (!lens.cellIds.includes(cellId)) {
      Logger.warn(
        "[lsp] CellId in completion request not found in current lens",
        {
          cellId,
          uri: params.textDocument.uri,
          availableCellIds: lens.cellIds,
        },
      );
    }

    const transformedPosition = lens.transformPosition(params.position, cellId);

    const response = await this.client.textDocumentCompletion({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: transformedPosition,
    });
    return normalizeCompletionResponse(response);
  }

  /**
   * Handle diagnostics from the server. We intercept notifications for publishDiagnostics
   * and shift ranges back to the local cell coordinates.
   */
  public patchProcessNotification() {
    invariant(
      "processNotification" in this.client,
      "processNotification is not a method on the client",
    );

    // @ts-expect-error: processNotification is private
    const previousProcessNotification = this.client.processNotification.bind(
      this.client,
    );

    const processNotification = (
      notification:
        | {
            method: "textDocument/publishDiagnostics";
            params: LSP.PublishDiagnosticsParams;
          }
        | { method: "other"; params: unknown },
    ) => {
      if (notification.method === "textDocument/publishDiagnostics") {
        Logger.debug("[lsp] handling diagnostics", notification);
        // Use the correct lens by version
        const payload = this.snapshotter.getLatestSnapshot();

        const diagnostics = notification.params.diagnostics;

        const { lens, version: cellVersion } = payload;

        // Pre-partition diagnostics by cell
        const diagnosticsByCellId = new Map<CellId, LSP.Diagnostic[]>();

        for (const diag of diagnostics) {
          // Each diagnostic can only belong to one cell
          for (const cellId of lens.cellIds) {
            if (lens.isInRange(diag.range, cellId)) {
              if (!diagnosticsByCellId.has(cellId)) {
                diagnosticsByCellId.set(cellId, []);
              }
              const cellDiag = {
                ...diag,
                range: lens.reverseRange(diag.range, cellId),
              };
              // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
              diagnosticsByCellId.get(cellId)!.push(cellDiag);
              break; // Exit inner loop once we find the matching cell
            }
          }
        }

        // Prune any cell URIs for cells that no longer exist
        const currentCellIds = new Set(lens.cellIds);
        NotebookLanguageServerClient.pruneSeenCellUris(currentCellIds);

        const cellsToClear = new Set(
          NotebookLanguageServerClient.SEEN_CELL_DOCUMENT_URIS,
        );

        // Process each cell's diagnostics
        for (const [cellId, cellDiagnostics] of diagnosticsByCellId.entries()) {
          Logger.debug("[lsp] diagnostics for cell", cellId, cellDiagnostics);
          const cellDocumentUri = CellDocumentUri.of(cellId);

          cellsToClear.delete(cellDocumentUri);

          previousProcessNotification({
            ...notification,
            params: {
              ...notification.params,
              uri: cellDocumentUri,
              version: cellVersion,
              diagnostics: cellDiagnostics,
            },
          });
        }

        // Clear the rest of the diagnostics
        if (cellsToClear.size > 0) {
          Logger.debug("[lsp] clearing diagnostics", cellsToClear);

          for (const cellDocumentUri of cellsToClear) {
            previousProcessNotification({
              method: "textDocument/publishDiagnostics",
              params: {
                uri: cellDocumentUri,
                diagnostics: [],
              },
            });
          }
        }

        return;
      }

      return previousProcessNotification(notification);
    };

    this.client.processNotification = processNotification;
  }
}
