/* Copyright 2024 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import { createTheme } from "thememirror";

export const darkTheme = [
  createTheme({
    variant: "dark",
    settings: {
      background: "#282c34",
      foreground: "#abb2bf",
      caret: "#528bff",
      selection: "#3E4451",
      lineHighlight: "#2c313c",
      gutterBackground: "var(--color-background)",
      gutterForeground: "var(--gray-10)",
    },
    styles: [
      { tag: t.comment, color: "#5c6370" },
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
    ".cm-reactive-variable": {
      fontWeight: "500",
      color: "#2a7aa5",
      borderBottom: "2px solid #bad3de",
    },
    ".cm-reactive-variable-hover": {
      cursor: "pointer",
      borderBottomWidth: "3px",
    },
  }),
];
