/* Copyright 2024 Marimo. All rights reserved. */
import {
  Compartment,
  Prec,
  type EditorState,
  type Extension,
  type Text,
} from "@codemirror/state";
import { keymap } from "@codemirror/view";
import { COPILOT_FILENAME, copilotServer, getCopilotClient } from "./client";
import {
  inlineCompletion,
  rejectInlineCompletion,
} from "@marimo-team/codemirror-ai";
import {
  copilotPlugin as codeiumCopilotPlugin,
  Language,
  codeiumOtherDocumentsConfig,
} from "@valtown/codemirror-codeium";
import { isCopilotEnabled } from "./state";
import { getCodes } from "./getCodes";
import type { CompletionConfig } from "@/core/config/config-schema";
import { Logger } from "@/utils/Logger";
import { languageAdapterState } from "../language/extension";
import { API } from "@/core/network/api";
import type { AiInlineCompletionRequest } from "@/core/kernel/messages";
import type { EditorView } from "@codemirror/view";
import { isInVimMode } from "../utils";
import {
  InlineCompletionTriggerKind,
  type InlineCompletionItem,
  type InlineCompletionList,
  type InlineCompletionParams,
} from "vscode-languageserver-protocol";

const copilotCompartment = new Compartment();

const logger = Logger.get("@github/copilot-language-server");

const commonInlineCompletionConfig = {
  delay: 500, // default is 500ms
  includeKeymap: true,
  events: {
    // Only show suggestions when the editor is focused
    shouldShowSuggestion: (view: EditorView) => view.hasFocus,
    beforeSuggestionFetch: (view: EditorView) => view.hasFocus,
  },
};

export const copilotBundle = (config: CompletionConfig): Extension => {
  if (process.env.NODE_ENV === "test") {
    return [];
  }

  const extensions: Extension[] = [];

  if (config.copilot === "codeium" && config.codeium_api_key) {
    extensions.push(
      codeiumCopilotPlugin({
        apiKey: config.codeium_api_key,
        language: Language.PYTHON,
      }),
      codeiumOtherDocumentsConfig.of({
        override: async () => {
          return [
            {
              text: getCodes(""),
              language: Language.PYTHON,
              editorLanguage: "python",
            },
          ];
        },
      }),
    );
  }

  if (config.copilot === "github") {
    extensions.push(
      inlineCompletion({
        ...commonInlineCompletionConfig,
        fetchFn: async (state) => {
          if (!isCopilotEnabled()) {
            return "";
          }

          // If no text, don't fetch
          if (state.doc.length === 0) {
            return "";
          }

          // wait 20ms so that the view is updated first
          await new Promise((resolve) => setTimeout(resolve, 20));

          const currentCode = state.doc.toString();
          const allCode = getCodes(currentCode);
          const request = getCopilotRequest(state, allCode);
          const response = await getCopilotClient().getCompletion(request);

          const suggestion = getSuggestion(response, request.position, state);
          return suggestion;
        },
      }),
    );
  }

  if (config.copilot === "custom") {
    extensions.push(
      inlineCompletion({
        ...commonInlineCompletionConfig,
        fetchFn: async (state) => {
          if (state.doc.length === 0) {
            return "";
          }

          // If not focused, don't fetch
          const prefix = state.doc.sliceString(0, state.selection.main.head);
          const suffix = state.doc.sliceString(
            state.selection.main.head,
            state.doc.length,
          );

          // If no prefix, don't fetch
          if (prefix.length === 0) {
            return "";
          }

          const language = state.field(languageAdapterState).type;
          let res = await API.post<AiInlineCompletionRequest, string>(
            "/ai/inline_completion",
            { prefix, suffix, language },
          );

          // Sometimes the prefix might get included in the response, so we need to trim it
          if (prefix && res.startsWith(prefix)) {
            res = res.slice(prefix.length);
          }
          if (suffix && res.endsWith(suffix)) {
            res = res.slice(0, -suffix.length);
          }

          return res;
        },
      }),
    );
  }

  return [
    ...extensions,
    Prec.highest(
      keymap.of([
        {
          key: "Escape",
          run: (view: EditorView) => {
            const status = rejectInlineCompletion(view);
            // When in vim mode, we need to propagate escape to exit insert mode.
            if (isInVimMode(view)) {
              return false;
            }
            return status;
          },
        },
      ]),
    ),
    // place in own compartment so it doesn't interfere with other LSP
    copilotCompartment.of(copilotServer()),
  ];
};

function getCopilotRequest(
  state: EditorState,
  allCode: string,
): InlineCompletionParams {
  // We need to update the position of the cursor because added newlines
  // from appending the other code
  const currentCode = state.doc.toString();
  const numberOfNewLines =
    allCode.split("\n").length - currentCode.split("\n").length;

  const position = offsetToPos(state.doc, state.selection.main.head);
  position.line += numberOfNewLines;
  return {
    textDocument: {
      uri: `file://${COPILOT_FILENAME}`,
      version: "replace_me" as unknown as number,
    },
    position: position,
    context: {
      triggerKind: InlineCompletionTriggerKind.Automatic,
    },
    formattingOptions: {
      tabSize: state.tabSize,
      insertSpaces: true,
    },
  } as InlineCompletionParams;
}

function getSuggestion(
  response: InlineCompletionList | InlineCompletionItem[] | null,
  userPosition: InlineCompletionParams["position"],
  state: EditorState,
): string {
  if (!response) {
    logger.debug("No response from copilot");
    return "";
  }

  const first = Array.isArray(response) ? response[0] : response.items[0];
  if (!first) {
    logger.debug("No response from copilot");
    return "";
  }

  const { insertText, range } = first;
  const insertTextString = String(insertText);

  if (!range) {
    logger.error("No range from copilot");
    return insertTextString;
  }

  // Calculate the start of the suggestion relative to the current position
  const startOffset = range.start.character - userPosition.character;

  // If startOffset is negative, we need to trim the beginning of displayText
  const resultText =
    startOffset < 0 ? insertTextString.slice(-startOffset) : insertTextString;

  // If the end of the suggestion already exists next in the document, we should trim it,
  // for example closing quotes, brackets, etc.
  // e.g
  // current content: print("hello|")
  //                     position ^
  // suggestion: world")
  // we need to remove the closing ") since we already have it
  //
  // See https://github.com/marimo-team/marimo/issues/830

  // Loop through from the whole word to the end of the suggestion
  // if we find a match, we trim it off the end of the suggestion
  const remainingText = state.doc.sliceString(
    state.selection.main.head,
    state.doc.length,
  );

  for (let i = 0; i < resultText.length; i++) {
    const remainingResultText = resultText.slice(i);
    if (remainingText.startsWith(remainingResultText)) {
      return resultText.slice(0, i);
    }
  }

  return resultText;
}

export const exportedForTesting = {
  getCopilotRequest,
  getSuggestion,
};

function offsetToPos(doc: Text, offset: number) {
  const line = doc.lineAt(offset);
  return {
    line: line.number - 1,
    character: offset - line.from,
  };
}
