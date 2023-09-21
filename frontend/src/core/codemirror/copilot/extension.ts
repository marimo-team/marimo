/* Copyright 2023 Marimo. All rights reserved. */
import { Extension, Text } from "@codemirror/state";
import {
  COPILOT_FILENAME,
  LANGUAGE_ID,
  copilotServer,
  getCopilotClient,
} from "./client";
import { inlineSuggestion } from "codemirror-extension-inline-suggestion";
import { isCopilotEnabled } from "./state";

export const copilotBundle = (): Extension => {
  if (process.env.NODE_ENV === "test") {
    return [];
  }

  return [
    inlineSuggestion({
      delay: 500, // default is 500ms
      fetchFn: async (view) => {
        if (!isCopilotEnabled()) {
          return "";
        }

        // wait 10ms so that the view is updated first
        await new Promise((resolve) => setTimeout(resolve, 10));
        const response = await getCopilotClient().getCompletion({
          doc: {
            source: view.doc.toString(),
            tabSize: view.tabSize,
            indentSize: 1,
            insertSpaces: true,
            path: COPILOT_FILENAME,
            version: 0,
            uri: `file://${COPILOT_FILENAME}`,
            relativePath: COPILOT_FILENAME,
            languageId: LANGUAGE_ID,
            position: offsetToPos(view.doc, view.selection.main.head),
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
