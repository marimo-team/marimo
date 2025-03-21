/* Copyright 2024 Marimo. All rights reserved. */
import {
  Compartment,
  type EditorState,
  type Extension,
  type Text,
} from "@codemirror/state";
import {
  COPILOT_FILENAME,
  LANGUAGE_ID,
  copilotServer,
  getCopilotClient,
} from "./client";
import { inlineSuggestion } from "codemirror-extension-inline-suggestion";
import {
  copilotPlugin as codeiumCopilotPlugin,
  Language,
  codeiumOtherDocumentsConfig,
} from "@valtown/codemirror-codeium";
import { isCopilotEnabled } from "./state";
import { getCodes } from "./getCodes";
import type { CompletionConfig } from "@/core/config/config-schema";
import type {
  CopilotGetCompletionsParams,
  CopilotGetCompletionsResult,
} from "./types";
import { Logger } from "@/utils/Logger";
import { languageAdapterState } from "../language/extension";
import { API } from "@/core/network/api";
import type { AiInlineCompletionRequest } from "@/core/kernel/messages";

const copilotCompartment = new Compartment();

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
      inlineSuggestion({
        delay: 500, // default is 500ms
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

          const suggestion = getSuggestion(
            response,
            request.doc.position,
            state,
          );
          if (suggestion) {
            Logger.debug("Copilot suggestion:", suggestion);
          }
          return suggestion;
        },
      }),
    );
  }

  if (config.copilot === "custom") {
    extensions.push(
      inlineSuggestion({
        delay: 500,
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

  return [...extensions, copilotServer()];
};

function getCopilotRequest(
  state: EditorState,
  allCode: string,
): CopilotGetCompletionsParams {
  // We need to update the position of the cursor because added newlines
  // from appending the other code
  const currentCode = state.doc.toString();
  const numberOfNewLines =
    allCode.split("\n").length - currentCode.split("\n").length;

  const position = offsetToPos(state.doc, state.selection.main.head);
  position.line += numberOfNewLines;

  return {
    doc: {
      source: allCode,
      tabSize: state.tabSize,
      indentSize: 1,
      insertSpaces: true,
      path: COPILOT_FILENAME,
      version: "replace_me" as unknown as number,
      uri: `file://${COPILOT_FILENAME}`,
      relativePath: COPILOT_FILENAME,
      languageId: LANGUAGE_ID,
      position: position,
    },
  };
}

function getSuggestion(
  response: CopilotGetCompletionsResult,
  userPosition: CopilotGetCompletionsParams["doc"]["position"],
  state: EditorState,
): string {
  // Empty (can happen if it is a stale request)
  if (response.completions.length === 0) {
    return "";
  }

  const { displayText, position: completionPosition } = response.completions[0];

  // Calculate the start of the suggestion relative to the current position
  const startOffset = completionPosition.character - userPosition.character;

  // If startOffset is negative, we need to trim the beginning of displayText
  const resultText =
    startOffset < 0 ? displayText.slice(-startOffset) : displayText;

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
