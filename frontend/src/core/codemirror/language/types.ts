/* Copyright 2024 Marimo. All rights reserved. */
import type { CompletionConfig, LSPConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import type { Extension } from "@codemirror/state";
import type { PlaceholderType } from "../config/extension";
import type { CellId } from "@/core/cells/ids";

/**
 * A language adapter is a class that can transform code from one language to
 * another. For example, a Markdown language adapter can make it feel like
 * you're writing Markdown, but it will actually be transformed into Python.
 */
export interface LanguageAdapter {
  readonly type: LanguageAdapterType;
  readonly defaultCode: string;
  transformIn(code: string): [string, number];
  transformOut(code: string): [string, number];
  isSupported(code: string): boolean;
  getExtension(
    cellId: CellId,
    completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
    placeholderType: PlaceholderType,
    lspConfig: LSPConfig,
  ): Extension[];
}

export type LanguageAdapterType = "python" | "markdown" | "sql";
