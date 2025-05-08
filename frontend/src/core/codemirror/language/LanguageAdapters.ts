/* Copyright 2024 Marimo. All rights reserved. */
import type { LanguageAdapter, LanguageAdapterType } from "./types";
import { PythonLanguageAdapter } from "./languages/python";
import { MarkdownLanguageAdapter } from "./languages/markdown";
import { SQLLanguageAdapter } from "./languages/sql";

export const LanguageAdapters: Record<LanguageAdapterType, LanguageAdapter> = {
  // Getters to prevent circular dependencies
  get python() {
    return new PythonLanguageAdapter();
  },
  get markdown() {
    return new MarkdownLanguageAdapter();
  },
  get sql() {
    return new SQLLanguageAdapter();
  },
};

export function getLanguageAdapters(): LanguageAdapter[] {
  return Object.values(LanguageAdapters);
}
