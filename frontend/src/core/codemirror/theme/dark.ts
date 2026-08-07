/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import { createTheme } from "thememirror";

export const darkTheme = [
  createTheme({
    variant: "dark",
    settings: {
      background: "var(--cm-background)",
      foreground: "#abb2bf",
      caret: "#528bff",
      selection: "var(--cm-selection-background)",
      lineHighlight: "#2c313c",
      gutterBackground: "var(--color-background)",
      gutterForeground: "var(--gray-10)",
    },
    styles: [
      { tag: t.comment, color: "var(--cm-comment)" },
      { tag: t.variableName, color: "#abb2bf" },
      { tag: [t.string, t.special(t.brace)], color: "#98c379" },
      { tag: t.number, color: "#d19a66" },
      { tag: t.bool, color: "#d19a66" },
      { tag: t.null, color: "#d19a66" },
      { tag: t.keyword, color: "#c678dd", fontWeight: 500 },
      { tag: t.className, color: "#61afef" },
      { tag: t.definition(t.typeName), color: "#61afef" },
      { tag: t.typeName, color: "#56b6c2" },
      { tag: t.angleBracket, color: "#abb2bf" },
      { tag: t.tagName, color: "#e06c75" },
      { tag: t.attributeName, color: "#d19a66" },
      { tag: t.operator, color: "#56b6c2", fontWeight: 500 },
      { tag: [t.function(t.variableName)], color: "#61afef" },
      { tag: [t.propertyName], color: "#e5c07b" },
    ],
  }),
  EditorView.theme({
    "&": {
      "--cm-selection-background": "var(--cm-selection-background-dark)",
    },
    ".mo-cm-reactive-reference": {
      fontWeight: "400",
      color: "var(--cm-reactive-reference-color-dark)",
      borderBottom: "2px solid var(--cm-reactive-reference-border-color)",
    },
    ".mo-cm-reactive-reference-hover": {
      cursor: "pointer",
    },
  }),
];
