/* Copyright 2024 Marimo. All rights reserved. */

import type { EditorView } from "@codemirror/view";
import type { LanguageServerClient } from "@marimo-team/codemirror-languageserver";
import type { DocumentUri } from "vscode-languageserver-protocol";
import type { CellId } from "@/core/cells/ids";
import { invariant } from "@/utils/invariant";
import type { TypedString } from "@/utils/typed";

export type ILanguageServerClient = {
  [key in keyof LanguageServerClient]: LanguageServerClient[key];
};

export type CellDocumentUri = DocumentUri & TypedString<"CellDocumentUri">;

export const CellDocumentUri = {
  PREFIX: "file:///",
  of(cellId: CellId): CellDocumentUri {
    return `${this.PREFIX}${cellId}` as CellDocumentUri;
  },
  is(uri: string): uri is CellDocumentUri {
    return uri.startsWith(this.PREFIX);
  },
  parse(uri: string): CellId {
    invariant(this.is(uri), `Invalid cell document URI: ${uri}`);
    return uri.slice(this.PREFIX.length) as CellId;
  },
};

/**
 * Notify is a @protected method on `LanguageServerClient`,
 * hiding public use with TypeScript.
 */
export function isClientWithNotify(
  client: ILanguageServerClient,
): client is ILanguageServerClient & {
  notify: (
    kind: string,
    options: { settings: Record<string, unknown> },
  ) => void;
} {
  return "notify" in client;
}

/**
 * Plugins are a @private on `LanguageServerClient`,
 * hiding public use with TypeScript.
 */
export function isClientWithPlugins(
  client: ILanguageServerClient,
): client is ILanguageServerClient & {
  plugins: Array<{ documentUri: string; view?: EditorView }>;
} {
  return "plugins" in client;
}
