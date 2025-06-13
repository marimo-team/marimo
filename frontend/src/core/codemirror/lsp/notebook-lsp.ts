/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import type * as LSP from "vscode-languageserver-protocol";
import type { CellId } from "@/core/cells/ids";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";
import { getTopologicalCodes } from "../copilot/getCodes";
import { createNotebookLens } from "./lens";
import { CellDocumentUri, type ILanguageServerClient } from "./types";
import { getLSPDocument } from "./utils";

export class NotebookLanguageServerClient implements ILanguageServerClient {
  public readonly documentUri: LSP.DocumentUri;
  private documentVersion = 0;
  private readonly client: ILanguageServerClient;

  /**
   * Map from the global document version to the cell id and version.
   */
  private versionToCellNumberAndVersion = new LRUCache<
    number,
    {
      cellDocumentUri: LSP.DocumentUri;
      version: number;
      lens: ReturnType<typeof createNotebookLens>;
    }
  >(20);

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
        "notify" in this.client,
        "notify is not a method on the client",
      );

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (this.client as any).notify("workspace/didChangeConfiguration", {
        settings: initialSettings,
      });
    });
  }

  textDocumentDefinition(
    params: LSP.DefinitionParams,
  ): Promise<LSP.Definition | LSP.LocationLink[] | null> {
    // Get the cell document URI from the params
    const cellDocumentUri = params.textDocument.uri;
    if (!CellDocumentUri.is(cellDocumentUri)) {
      Logger.warn("Invalid cell document URI", cellDocumentUri);
      return Promise.resolve(null);
    }

    // Find the lens for this cell
    const cellId = CellDocumentUri.parse(cellDocumentUri);
    const versionInfo = [...this.versionToCellNumberAndVersion.values()].find(
      (info) => info.cellDocumentUri === cellDocumentUri,
    );

    if (!versionInfo) {
      Logger.warn("No lens found for cell", cellId);
      return Promise.resolve(null);
    }

    // Use the lens to transform the position
    const { lens } = versionInfo;
    const transformedPosition = lens.transformPosition(params.position, cellId);

    return this.client.textDocumentDefinition({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: transformedPosition,
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

    const cellId = CellDocumentUri.parse(cellDocumentUri);
    const versionInfo = [...this.versionToCellNumberAndVersion.values()].find(
      (info) => info.cellDocumentUri === cellDocumentUri,
    );

    if (!versionInfo) {
      Logger.warn("No lens found for cell", cellId);
      return null;
    }

    const { lens } = versionInfo;
    const transformedPosition = lens.transformPosition(params.position, cellId);

    const response = await this.client.textDocumentSignatureHelp({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: transformedPosition,
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

    // Find the latest lens
    const latestVersion = [...this.versionToCellNumberAndVersion.keys()].at(-1);
    if (latestVersion === undefined) {
      Logger.warn("No lens found for cell", cellDocumentUri);
      return null;
    }

    // Use the lens to transform the position
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const { lens } = this.versionToCellNumberAndVersion.get(latestVersion)!;
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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const plugin of (this.client as any).plugins) {
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

      const view: EditorView = plugin.view;
      if (!view) {
        Logger.warn("No view for plugin", plugin);
        continue;
      }

      // Only update if it has changed
      if (view.state.doc.toString() !== newCode) {
        view.dispatch({
          changes: { from: 0, to: view.state.doc.length, insert: newCode },
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

    // Get the latest updated lens
    const latestVersion = [...this.versionToCellNumberAndVersion.keys()].at(-1);
    if (!latestVersion) {
      Logger.warn("No lens found for cell", cellDocumentUri);
      return null;
    }

    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    const { lens } = this.versionToCellNumberAndVersion.get(latestVersion)!;
    const cellId = CellDocumentUri.parse(cellDocumentUri);

    return this.client.textDocumentPrepareRename({
      ...params,
      textDocument: {
        uri: this.documentUri,
      },
      position: lens.transformPosition(params.position, cellId),
    });
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
    return getTopologicalCodes();
  }

  /**
   * Example of "zoom in" for textDocumentDidOpen, so server sees a merged doc.
   */
  public async textDocumentDidOpen(params: LSP.DidOpenTextDocumentParams) {
    Logger.debug("[lsp] textDocumentDidOpen", params);
    const cellDocumentUri = params.textDocument.uri;
    const { cellIds, codes } = this.getNotebookCode();
    const lens = createNotebookLens(cellIds, codes);

    // Store lens keyed by document version
    const version = params.textDocument.version;
    this.versionToCellNumberAndVersion.set(this.documentVersion, {
      cellDocumentUri,
      version,
      lens,
    });
    invariant(
      CellDocumentUri.is(cellDocumentUri),
      "Execpted URI to be CellDocumentUri",
    );
    NotebookLanguageServerClient.SEEN_CELL_DOCUMENT_URIS.add(cellDocumentUri);

    // Pass merged doc to super
    const result = await this.client.textDocumentDidOpen({
      textDocument: {
        languageId: params.textDocument.languageId,
        text: lens.mergedText,
        uri: this.documentUri,
        version: this.documentVersion,
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

  public async textDocumentDidChange(params: LSP.DidChangeTextDocumentParams) {
    Logger.debug("[lsp] textDocumentDidChange", params);
    // We know how to only handle single content changes
    // But that is all we expect to receive
    if (params.contentChanges.length === 1) {
      const cellDocumentUri = params.textDocument.uri;
      const { cellIds, codes } = this.getNotebookCode();
      const lens = createNotebookLens(cellIds, codes);

      const version = params.textDocument.version;
      this.documentVersion++;
      const globalDocumentVersion = this.documentVersion;

      this.versionToCellNumberAndVersion.set(globalDocumentVersion, {
        cellDocumentUri,
        version,
        lens,
      });

      // Update changes for merged doc, etc.
      return this.client.textDocumentDidChange({
        textDocument: {
          uri: this.documentUri,
          version: globalDocumentVersion,
        },
        contentChanges: [{ text: lens.mergedText }],
      });
    }

    Logger.warn("[lsp] Unhandled textDocumentDidChange", params);

    return this.client.textDocumentDidChange(params);
  }

  public async textDocumentHover(params: LSP.HoverParams) {
    Logger.debug("[lsp] textDocumentHover", params);

    const latestVersion = [...this.versionToCellNumberAndVersion.keys()].at(-1);
    if (latestVersion === undefined) {
      Logger.debug("[lsp] no latest version");
      return this.client.textDocumentHover(params);
    }
    const payload = this.versionToCellNumberAndVersion.get(latestVersion);
    if (!payload) {
      Logger.debug("[lsp] no payload for latest version");
      return this.client.textDocumentHover(params);
    }
    const { lens, cellDocumentUri } = payload;
    const cellId = CellDocumentUri.parse(cellDocumentUri);

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
        value: `<div class="docs-documentation mo-cm-tooltip">\n${hover.contents.value}\n</div>`,
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
    const latestVersion = [...this.versionToCellNumberAndVersion.keys()].at(-1);

    if (latestVersion === undefined) {
      return this.client.textDocumentCompletion(params);
    }

    const payload = this.versionToCellNumberAndVersion.get(latestVersion);
    if (!payload) {
      return this.client.textDocumentCompletion(params);
    }

    const { lens, cellDocumentUri } = payload;
    const cellId = CellDocumentUri.parse(cellDocumentUri);

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
        const globalVersion = notification.params.version || 0;
        const payload = this.versionToCellNumberAndVersion.get(globalVersion);

        if (!payload) {
          Logger.warn("[lsp] missing payload for version", globalVersion);
          return previousProcessNotification(notification);
        }

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
