/* Copyright 2024 Marimo. All rights reserved. */
import type * as LSP from "vscode-languageserver-protocol";
import { LanguageServerClient } from "codemirror-languageserver";
import { getTopologicalCodes } from "../copilot/getCodes";
import { LRUCache } from "@/utils/lru";
import { createNotebookLens } from "./lens";

// @ts-expect-error Extending private class
export class NotebookLanguageServerClient extends LanguageServerClient {
  private lensByVersion = new LRUCache<
    number,
    ReturnType<typeof createNotebookLens>
  >(10);

  private getNotebookCode() {
    return getTopologicalCodes();
  }

  /**
   * Example of "zoom in" for textDocumentDidOpen, so server sees a merged doc.
   */
  public override textDocumentDidOpen(params: LSP.DidOpenTextDocumentParams) {
    const currentCell = params.textDocument.text;
    const lens = createNotebookLens(currentCell, this.getNotebookCode());

    // Store lens keyed by document version
    const version = params.textDocument.version || 0;
    this.lensByVersion.set(version, lens);

    // Pass merged doc to super
    return super.textDocumentDidOpen({
      ...params,
      textDocument: {
        ...params.textDocument,
        text: lens.mergedText,
      },
    });
  }

  public override async textDocumentDidChange(
    params: LSP.DidChangeTextDocumentParams,
  ) {
    // Example of updating the lens after changes
    if (params.contentChanges.length === 1) {
      const newCell = params.contentChanges[0].text;
      const otherCells = this.getNotebookCode();
      const lens = createNotebookLens(newCell, otherCells);

      const version = params.textDocument.version ?? 0;
      this.lensByVersion.set(version, lens);

      // Update changes for merged doc, etc.
      return super.textDocumentDidChange({
        ...params,
        contentChanges: [
          {
            text: getTopologicalCodes().join("\n"),
          },
        ],
      });
    }

    return super.textDocumentDidChange(params);
  }

  public override async textDocumentHover(params: LSP.HoverParams) {
    const latestVersion = [...this.lensByVersion.keys()].at(-1);
    if (latestVersion === undefined) {
      return super.textDocumentHover(params);
    }
    const lens = this.lensByVersion.get(latestVersion);
    if (!lens) {
      return super.textDocumentHover(params);
    }

    const hover = await super.textDocumentHover({
      ...params,
      position: lens.transformPosition(params.position),
    });
    if (!hover) {
      return hover;
    }

    // Convert ranges back to cell coordinates
    if (hover.range) {
      hover.range = lens.reverseRange(hover.range);
    }
    return hover;
  }

  public override async textDocumentCompletion(params: LSP.CompletionParams) {
    return super.textDocumentCompletion(params);
  }

  /**
   * Handle diagnostics from the server. We intercept notifications for publishDiagnostics
   * and shift ranges back to the local cell coordinates.
   */
  public override processNotification(
    notification:
      | {
          method: "textDocument/publishDiagnostics";
          params: LSP.PublishDiagnosticsParams;
        }
      | {
          method: "other";
          params: unknown;
        },
  ) {
    if (
      notification.method === "textDocument/publishDiagnostics" &&
      notification.params?.diagnostics
    ) {
      // Use the correct lens by version
      const version = notification.params.version || 0;
      const lens = this.lensByVersion.get(version);
      if (lens) {
        for (const diag of notification.params.diagnostics) {
          diag.range = lens.reverseRange(diag.range);
        }
        // Remove diagnostics the come from other cells
        // These are outside the size of the current cell
        notification.params.diagnostics =
          notification.params.diagnostics.filter((diag) =>
            lens.isInRange(diag.range),
          );
      }
    }
    // @ts-expect-error: processNotification is private
    return super.processNotification(notification);
  }
}
