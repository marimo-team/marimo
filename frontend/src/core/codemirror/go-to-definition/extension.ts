/* Copyright 2024 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { createUnderlinePlugin, underlineField } from "./underline";
import { goToDefinition } from "./utils";

/**
 * Create a go-to-definition extension.
 */
export function goToDefinitionBundle() {
  return [
    underlineField,
    createUnderlinePlugin((view, variableName) => {
      goToDefinition(view, variableName);
    }),
    EditorView.baseTheme({
      ".underline": {
        textDecoration: "underline",
        cursor: "pointer",
        color: "var(--link)",
      },
    }),
  ];
}
