/* Copyright 2026 Marimo. All rights reserved. */
import { EditorView } from "@codemirror/view";
import { createUnderlinePlugin, underlineField } from "./underline";
import { goToDefinitionWithLspFallback } from "./utils";

const underlineTheme = EditorView.baseTheme({
  ".underline": {
    textDecoration: "underline",
    cursor: "pointer",
    color: "var(--link)",
  },
});

/**
 * Create a go-to-definition extension.
 */
export function goToDefinitionBundle() {
  return [
    underlineField,
    createUnderlinePlugin((view) => {
      goToDefinitionWithLspFallback(view);
    }),
    underlineTheme,
  ];
}
