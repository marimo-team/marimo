/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { createUnderlinePlugin, underlineField } from "./underline";
import { goToDefinitionWithLspFallback } from "./utils";

/**
 * Create a go-to-definition extension.
 */
export function goToDefinitionBundle() {
  return [
    underlineField,
    createUnderlinePlugin((view) => {
      goToDefinitionWithLspFallback(view);
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
