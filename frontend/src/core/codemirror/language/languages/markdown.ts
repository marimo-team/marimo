/* Copyright 2026 Marimo. All rights reserved. */

import { autocompletion } from "@codemirror/autocomplete";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { python, pythonLanguage } from "@codemirror/lang-python";
import { StreamLanguage } from "@codemirror/language";
import { languages } from "@codemirror/language-data";
import { stexMath } from "@codemirror/legacy-modes/mode/stex";
import type { Extension } from "@codemirror/state";
import { type EditorView, ViewPlugin } from "@codemirror/view";
import {
  type MarkdownMetadata,
  MarkdownParser,
} from "@marimo-team/smart-cells";
import type { CellId } from "@/core/cells/ids";
import type { CompletionConfig } from "@/core/config/config-schema";
import type { HotkeyProvider } from "@/core/hotkeys/hotkeys";
import { markdownAutoRunExtension } from "../../cells/extensions";
import { pythonCompletionSource } from "../../completion/completer";
import { conditionalCompletion } from "../../completion/utils";
import type { PlaceholderType } from "../../config/types";
import { markdownCompletionSources } from "../../markdown/completions";
import { enhancedMarkdownExtension } from "../../markdown/extension";
import { parsePython } from "../embedded/embedded-python";
import { parseLatex } from "../embedded/latex";
import { languageMetadataField } from "../metadata";
import type { LanguageAdapter } from "../types";

export type MarkdownLanguageAdapterMetadata = MarkdownMetadata;

/**
 * Default hide_code setting for markdown cells.
 * When true, the markdown code is hidden after the cell is blurred,
 * showing only the rendered output.
 */
export const MARKDOWN_INITIAL_HIDE_CODE = true;

/**
 * Language adapter for Markdown.
 */
export class MarkdownLanguageAdapter
  implements LanguageAdapter<MarkdownLanguageAdapterMetadata>
{
  private parser = new MarkdownParser();

  readonly type = "markdown";
  readonly defaultCode = this.parser.defaultCode;
  readonly defaultMetadata: MarkdownLanguageAdapterMetadata =
    this.parser.defaultMetadata;

  static fromMarkdown(markdown: string) {
    return MarkdownParser.fromMarkdown(markdown);
  }

  transformIn(
    pythonCode: string,
  ): [string, number, MarkdownLanguageAdapterMetadata] {
    const result = this.parser.transformIn(pythonCode);
    return [result.code, result.offset, result.metadata];
  }

  transformOut(
    code: string,
    metadata: MarkdownLanguageAdapterMetadata,
  ): [string, number] {
    const result = this.parser.transformOut(code, metadata);
    return [result.code, result.offset];
  }

  isSupported(pythonCode: string): boolean {
    return this.parser.isSupported(pythonCode);
  }

  getExtension(
    _cellId: CellId,
    _completionConfig: CompletionConfig,
    hotkeys: HotkeyProvider,
    _: PlaceholderType,
  ): Extension[] {
    const markdownLanguageData = markdown().language.data;
    let view: EditorView | undefined;

    // Only activate completions for f-strings
    const isFStringActive = () => {
      if (!view) {
        return true;
      }

      const metadata = view?.state.field(languageMetadataField);
      if (metadata === undefined) {
        return false;
      }
      return metadata.quotePrefix?.includes("f") ?? false;
    };

    return [
      ViewPlugin.define((_view) => {
        view = _view;
        return {};
      }),
      markdown({
        base: markdownLanguage,
        codeLanguages: languages,
        extensions: [
          // Embedded LateX in Markdown
          parseLatex(StreamLanguage.define(stexMath).parser),
          // Embedded Python in Markdown
          parsePython(pythonLanguage.parser, isFStringActive),
        ],
      }),
      enhancedMarkdownExtension(hotkeys),
      // Completions for markdown
      markdownCompletionSources.map((source) =>
        markdownLanguageData.of({ autocomplete: source }),
      ),
      // Completions for embedded Python
      python().language.data.of({
        autocomplete: conditionalCompletion({
          completion: pythonCompletionSource,
          predicate: isFStringActive,
        }),
      }),

      autocompletion({
        // We remove the default keymap because we use our own which
        // handles the Escape key correctly in Vim
        defaultKeymap: false,
        activateOnTyping: true,
      }),
      // Markdown autorun
      markdownAutoRunExtension({ predicate: () => !isFStringActive() }),
    ];
  }
}
