/* Copyright 2024 Marimo. All rights reserved. */
import type * as LSP from "vscode-languageserver-protocol";
import { getTopologicalCodes } from "../copilot/getCodes";
import { createNotebookLens } from "./lens";
import { CellDocumentUri, type ILanguageServerClient } from "./types";
import { invariant } from "@/utils/invariant";
import { Logger } from "@/utils/Logger";
import { LRUCache } from "@/utils/lru";
import type { CellId } from "@/core/cells/ids";
import { getFilenameFromDOM } from "@/core/dom/htmlUtils";

export class NotebookLanguageServerClient implements ILanguageServerClient {
  private readonly documentUri =
    `file://${getFilenameFromDOM() ?? "/__marimo_notebook__.py"}`;
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

  private static readonly SEEN_CELL_DOCUMENT_URIS = new Set<LSP.DocumentUri>();

  constructor(client: ILanguageServerClient, initialSettings: any) {
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
    return this.client.textDocumentDefinition(params);
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

  textDocumentRename(
    params: LSP.RenameParams,
  ): Promise<LSP.WorkspaceEdit | null> {
    return this.client.textDocumentRename(params);
  }

  completionItemResolve(
    params: LSP.CompletionItem,
  ): Promise<LSP.CompletionItem> {
    return this.client.completionItemResolve(params);
  }

  textDocumentPrepareRename(
    params: LSP.PrepareRenameParams,
  ): Promise<LSP.PrepareRenameResult | null> {
    return this.client.textDocumentPrepareRename(params);
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
      const globalDocumentVersion = this.documentVersion + 1;

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

        // Filter out ignored diagnostics
        // Keep it if there is no code
        const diagnostics = notification.params.diagnostics.filter(
          (diag) => !diag.code || !IGNORED_DIAGNOSTICS.has(diag.code),
        );

        // If diagnostics are empty, we can just clear them for all cells
        if (diagnostics.length === 0) {
          Logger.debug("[lsp] clearing diagnostics");

          for (const cellDocumentUri of NotebookLanguageServerClient.SEEN_CELL_DOCUMENT_URIS) {
            previousProcessNotification({
              method: "textDocument/publishDiagnostics",
              params: {
                uri: cellDocumentUri,
                diagnostics: [],
              },
            });
          }
          return;
        }

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

        // Process each cell's diagnostics
        for (const [cellId, cellDiagnostics] of diagnosticsByCellId.entries()) {
          Logger.debug("[lsp] diagnostics for cell", cellId, cellDiagnostics);

          previousProcessNotification({
            ...notification,
            params: {
              ...notification.params,
              uri: CellDocumentUri.of(cellId),
              version: cellVersion,
              diagnostics: cellDiagnostics,
            },
          });
        }

        return;
      }

      return previousProcessNotification(notification);
    };

    this.client.processNotification = processNotification;
  }
}

const IGNORED_DIAGNOSTICS = new Set<string | number>([
  "E402", // Module level import not at top of file
]);
