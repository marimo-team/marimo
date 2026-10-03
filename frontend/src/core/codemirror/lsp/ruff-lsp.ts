/* Copyright 2026 Marimo. All rights reserved. */

import { NotebookLanguageServerClient } from "./notebook-lsp";
import type { ILanguageServerClient } from "./types";

// Match the notebook exclusions used by pylsp's Ruff plugin. Filter results
// instead of setting lint.ignore, which would override project configuration.
const IGNORED_DIAGNOSTIC_CODES = new Set([
  "D100", // Notebooks use markdown instead of module docstrings.
  "D103", // Missing docstring in public function.
  "W292", // The last cell does not need a trailing newline.
  "E402", // Imports can appear in any cell.
  "E302", // Cells are joined without extra blank lines.
  "E305",
  "B018", // A final expression displays the cell's output.
  "I001", // Imports can be spread across cells.
]);

export class RuffLanguageServerClient extends NotebookLanguageServerClient {
  public override hasCapability(method: string): boolean {
    // Ruff hover describes lint rules rather than Python symbols.
    return method !== "textDocument/hover" && super.hasCapability(method);
  }

  public override onNotification(
    listener: Parameters<ILanguageServerClient["onNotification"]>[0],
  ): () => boolean {
    return super.onNotification((notification) => {
      if (notification.method !== "textDocument/publishDiagnostics") {
        listener(notification);
        return;
      }
      listener({
        ...notification,
        params: {
          ...notification.params,
          diagnostics: notification.params.diagnostics.filter(
            (diagnostic) =>
              !IGNORED_DIAGNOSTIC_CODES.has(String(diagnostic.code)),
          ),
        },
      });
    });
  }
}
