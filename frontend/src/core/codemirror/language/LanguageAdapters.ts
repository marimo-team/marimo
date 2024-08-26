/* Copyright 2024 Marimo. All rights reserved. */
import type { LanguageAdapter, LanguageAdapterType } from "./types";
import { PythonLanguageAdapter } from "./python";
import { MarkdownLanguageAdapter } from "./markdown";
import { SQLLanguageAdapter } from "./sql";

export const LanguageAdapters: Record<
  LanguageAdapterType,
  () => LanguageAdapter
> = {
  python: () => new PythonLanguageAdapter(),
  markdown: () => new MarkdownLanguageAdapter(),
  sql: () => new SQLLanguageAdapter(),
};

export function getLanguageAdapters() {
  return Object.values(LanguageAdapters).map((la) => la());
}
