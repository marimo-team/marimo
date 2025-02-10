/* Copyright 2024 Marimo. All rights reserved. */
import type { CellId } from "@/core/cells/ids";
import { invariant } from "@/utils/invariant";
import type { LanguageServerClient } from "@marimo-team/codemirror-languageserver";
import type { DocumentUri } from "vscode-languageserver-protocol";

export type ILanguageServerClient = {
  [key in keyof LanguageServerClient]: LanguageServerClient[key];
};

export const CellDocumentUri = {
  PREFIX: "file:///",
  of(cellId: CellId): DocumentUri {
    return `${this.PREFIX}${cellId}`;
  },
  is(uri: string): uri is DocumentUri {
    return uri.startsWith(this.PREFIX);
  },
  parse(uri: string): CellId {
    invariant(this.is(uri), `Invalid cell document URI: ${uri}`);
    return uri.slice(this.PREFIX.length) as CellId;
  },
};
