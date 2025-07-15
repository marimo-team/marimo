/* Copyright 2024 Marimo. All rights reserved. */

import type * as LSP from "vscode-languageserver-protocol";
import type { CellId } from "@/core/cells/ids";
import { store } from "@/core/state/jotai";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";
import { topologicalCodesAtom } from "../copilot/getCodes";
import { createNotebookLens, type NotebookLens } from "./lens";
import {
  CellDocumentUri,
  type ILanguageServerClient,
  isClientWithNotify,
  isClientWithPlugins,
} from "./types";
import { getLSPDocument } from "./utils";

class Snapshotter {
  private documentVersion = 0;

  constructor(
    private readonly getNotebookCode: () => {
      cellIds: CellId[];
      codes: Record<CellId, string>;
    },
  ) {}

  /**
   * Map from the global document version to the cell id and version.
   */
  private versionToCellNumberAndVersion = new LRUCache<number, NotebookLens>(
    20,
  );

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

  public getSnapshot(version: number) {
    const snapshot = this.versionToCellNumberAndVersion.get(version);
    if (!snapshot) {
      throw new Error(`No snapshot for version ${version}`);
    }
    return snapshot;
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

export class NotebookLanguageServerClient implements ILanguageServerClient {
  public readonly documentUri: LSP.DocumentUri;
  private readonly client: ILanguageServerClient;
  private readonly snapshotter: Snapshotter;

  private static readonly SEEN_CELL_DOCUMENT_URIS = new Set<CellDocumentUri>();

  constructor(
    client: ILanguageServerClient,
    initialSettings: Record<string, unknown>,
  ) {
    this.documentUri = getLSPDocument();

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

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  detachPlugin(plugin: any): void {
    this.client.detachPlugin(plugin);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  attachPlugin(plugin: any): void {
    this.client.attachPlugin(plugin);
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

  async sync(): Promise<LSP.DidChangeTextDocumentParams> {
    const { lens, version, didChange } = this.snapshotter.snapshot();
    if (!didChange) {
      return {
        textDocument: {
          uri: this.documentUri,
          version: version,
        },
        contentChanges: [{ text: lens.mergedText }],
      };
    }

    // Update changes for merged doc, etc.
    return this.client.textDocumentDidChange({
      textDocument: {
        uri: this.documentUri,
        version: version,
      },
      contentChanges: [{ text: lens.mergedText }],
    });
  }

  public async textDocumentDidChange(params: LSP.DidChangeTextDocumentParams) {
    Logger.debug("[lsp] textDocumentDidChange", params);
    // We know how to only handle single content changes
    // But that is all we expect to receive
    if (params.contentChanges.length === 1) {
      return this.sync();
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

    // This LSP method has no version, so lets sync and then get the latest snapshot
    await this.sync();
    const { lens } = this.snapshotter.getLatestSnapshot();

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

    // This LSP method has no version, so lets sync and then get the latest snapshot
    await this.sync();
    const { lens } = this.snapshotter.getLatestSnapshot();

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

    return response;
  }

  textDocumentCodeAction(
    params: LSP.CodeActionParams,
  ): Promise<Array<LSP.Command | LSP.CodeAction> | null> {
    const disabledCodeAction = true;
    if (disabledCodeAction) {
      return Promise.resolve(null);
    }
    return this.client.textDocumentCodeAction(params);
  }

  /**
   * HACK
   * This whole function is a hack to work around the fact that we don't have
   * a great way to map the edits back to the appropriate LSP view plugin.
   *
   * Instead, we parse out the new text from the response and then update the
   * code in the plugins manually, instead of using the LSP.
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

    // This LSP method has no version, so lets sync and then get the latest snapshot
    await this.sync();
    const { lens } = this.snapshotter.getLatestSnapshot();

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

    invariant(
      isClientWithPlugins(this.client),
      "Expected client with plugins.",
    );

    // Update the code in the plugins manually
    for (const plugin of this.client.plugins) {
      const documentUri: string = plugin.documentUri;
      if (!CellDocumentUri.is(documentUri)) {
        Logger.warn("Invalid cell document URI", documentUri);
        continue;
      }

      const cellId = CellDocumentUri.parse(documentUri);
      const newCode = editsToNewCode.get(cellId);
      if (newCode == null) {
        Logger.warn("No new code for cell", cellId);
        continue;
      }

      if (!plugin.view) {
        Logger.warn("No view for plugin", plugin);
        continue;
      }

      // Only update if it has changed
      if (plugin.view.state.doc.toString() !== newCode) {
        plugin.view.dispatch({
          changes: {
            from: 0,
            to: plugin.view.state.doc.length,
            insert: newCode,
          },
        });
      }
    }

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

  completionItemResolve(
    params: LSP.CompletionItem,
  ): Promise<LSP.CompletionItem> {
    return this.client.completionItemResolve(params);
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

    // This LSP method has no version, so lets sync and then get the latest snapshot
    await this.sync();
    const { lens } = this.snapshotter.getLatestSnapshot();

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

    // This LSP method has no version, so lets sync and then get the latest snapshot
    await this.sync();
    const { lens } = this.snapshotter.getLatestSnapshot();

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
    // This LSP method has no version, so lets sync and then get the latest snapshot
    await this.sync();
    const { lens } = this.snapshotter.getLatestSnapshot();
    const cellId = CellDocumentUri.parse(params.textDocument.uri);

    return this.client.textDocumentCompletion({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: lens.transformPosition(params.position, cellId),
    });
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
