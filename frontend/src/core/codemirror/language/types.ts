/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import type { Extension } from "@codemirror/state";
import type { CellId } from "@/core/cells/ids";
import type {
  CompletionConfig,
  DiagnosticsConfig,
  LSPConfig,
} from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { PlaceholderType } from "../config/types";

/**
 * A language adapter is a class that can transform code from one language to
 * another. For example, a Markdown language adapter can make it feel like
 * you're writing Markdown, but it will actually be transformed into Python.
 *
 * These are stateless classes that can be reused across multiple editor views.
 */
export interface LanguageAdapter<M = Record<string, any>> {
  readonly type: LanguageAdapterType;
  readonly defaultCode: string;
  readonly defaultMetadata: Readonly<M>;

  transformIn(code: string): [string, number, M];
  transformOut(code: string, metadata: M): [string, number];
  isSupported(code: string): boolean;
  getExtension(
    cellId: CellId,
    completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
    placeholderType: PlaceholderType,
    lspConfig: LSPConfig & { diagnostics?: DiagnosticsConfig },
  ): Extension[];
}

export type LanguageMetadataOf<T extends LanguageAdapter> =
  T extends LanguageAdapter<infer M> ? M : never;

export type LanguageAdapterType = "python" | "markdown" | "sql";
