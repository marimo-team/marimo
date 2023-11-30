/* Copyright 2023 Marimo. All rights reserved. */
import { Extension } from "@codemirror/state";

/**
 * A language adapter is a class that can transform code from one language to
 * another. For example, a Markdown language adapter can make it feel like
 * you're writing Markdown, but it will actually be transformed into Python.
 */
export interface LanguageAdapter {
  type: string;
  transformIn(code: string): [string, number];
  transformOut(code: string): [string, number];
  isSupported(code: string): boolean;
  getExtension(): Extension;
}
