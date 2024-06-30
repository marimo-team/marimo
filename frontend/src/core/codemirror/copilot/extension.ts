/* Copyright 2024 Marimo. All rights reserved. */
import { Extension, Text } from "@codemirror/state";
import {
  COPILOT_FILENAME,
  LANGUAGE_ID,
  copilotServer,
  getCopilotClient,
} from "./client";
import { inlineSuggestion } from "codemirror-extension-inline-suggestion";
import {
  copilotPlugin,
  Language,
  codeiumOtherDocumentsConfig,
} from "@valtown/codemirror-codeium";
import { isCopilotEnabled } from "./state";
import { getCodes } from "./getCodes";
import { CompletionConfig } from "@/core/config/config-schema";

export const copilotBundle = (config: CompletionConfig): Extension => {
  if (process.env.NODE_ENV === "test") {
    return [];
  }

  return [
    config.codeium_api_key
      ? [
          copilotPlugin({
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
        ]
      : [],
    inlineSuggestion({
      delay: 200, // default is 500ms
      fetchFn: async (view) => {
        if (config.codeium_api_key) {
          return "";
        }
        if (!isCopilotEnabled()) {
          return "";
        }

        // If no text, don't fetch
        if (view.doc.length === 0) {
          return "";
        }

        // wait 10ms so that the view is updated first
        await new Promise((resolve) => setTimeout(resolve, 10));

        // We need to update the position of the cursor because added newlines
        // from appending the other code
        const currentCode = view.doc.toString();
        const allCode = getCodes(currentCode);
        const numberOfNewLines =
          allCode.split("\n").length - currentCode.split("\n").length;

        const position = offsetToPos(view.doc, view.selection.main.head);
        position.line += numberOfNewLines;

        const response = await getCopilotClient().getCompletion({
          doc: {
            source: allCode,
            tabSize: view.tabSize,
            indentSize: 1,
            insertSpaces: true,
            path: COPILOT_FILENAME,
            version: 0,
            uri: `file://${COPILOT_FILENAME}`,
            relativePath: COPILOT_FILENAME,
            languageId: LANGUAGE_ID,
            position: position,
          },
        });
        return response.completions.map((c) => c.displayText)[0] ?? "";
      },
    }),
    // pop off last 2 elements of the array which are tooltip and autocompletion
    copilotServer().slice(0, -2),
  ];
};

function offsetToPos(doc: Text, offset: number) {
  const line = doc.lineAt(offset);
  return {
    line: line.number - 1,
    character: offset - line.from,
  };
}
