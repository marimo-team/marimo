/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import { createTheme } from "thememirror";

export const lightTheme = [
  createTheme({
    variant: "light",
    settings: {
      background: "#ffffff",
      foreground: "var(--cm-foreground)",
      caret: "#000000",
      selection: "var(--cm-selection-background)",
      lineHighlight: "#cceeff44",
      gutterBackground: "var(--color-background)",
      gutterForeground: "var(--gray-10)",
    },
    styles: [
      // Default codemirror light theme
      { tag: t.comment, color: "var(--cm-comment)" },
      { tag: t.variableName, color: "var(--cm-foreground)" },
      { tag: [t.string, t.special(t.brace)], color: "var(--cm-string)" },
      { tag: t.number, color: "var(--cm-number)" },
      { tag: t.bool, color: "var(--cm-atom)" },
      { tag: t.null, color: "var(--cm-atom)" },
      { tag: t.keyword, color: "var(--cm-keyword)", fontWeight: 500 },
      // { tag: t.operator, color: '#000' },
      { tag: t.className, color: "var(--cm-class-name)" },
      { tag: t.definition(t.typeName), color: "var(--cm-class-name)" },
      { tag: t.typeName, color: "var(--cm-type-name)" },
      { tag: t.angleBracket, color: "var(--cm-foreground)" },
      { tag: t.tagName, color: "var(--cm-tag-name)" },
      { tag: t.attributeName, color: "var(--cm-attribute-name)" },
      // Adjustments
      { tag: t.operator, color: "var(--cm-operator)", fontWeight: 500 },
      {
        tag: [t.function(t.variableName)],
        color: "var(--cm-function)",
      },
      {
        tag: [t.propertyName],
        color: "var(--cm-property)",
      },
    ],
  }),
  EditorView.theme({
    "&": {
      "--cm-selection-background": "var(--cm-selection-background-light)",
    },
    ".mo-cm-reactive-reference": {
      fontWeight: "400",
      color: "var(--cm-reactive-reference-color-light)",
      borderBottom: "2px solid var(--cm-reactive-reference-border-color)",
    },
    ".mo-cm-reactive-reference-hover": {
      cursor: "pointer",
    },
  }),
];
