/* Copyright 2024 Marimo. All rights reserved. */
import { CompletionConfig } from "@/core/config/config-schema";
import { Extension } from "@codemirror/state";

/**
 * A language adapter is a class that can transform code from one language to
 * another. For example, a Markdown language adapter can make it feel like
 * you're writing Markdown, but it will actually be transformed into Python.
 */
export interface LanguageAdapter {
  type: "python" | "markdown";
  transformIn(code: string): [string, number];
  transformOut(code: string): [string, number];
  isSupported(code: string): boolean;
  getExtension(completionConfig: CompletionConfig): Extension;
}
