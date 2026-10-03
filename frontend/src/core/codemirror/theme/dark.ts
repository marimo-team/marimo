/* Copyright 2026 Marimo. All rights reserved. */

import { EditorView } from "@codemirror/view";
import { tags as t } from "@lezer/highlight";
import { createTheme } from "thememirror";

export const darkTheme = [
  createTheme({
    variant: "dark",
    settings: {
      background: "var(--cm-background)",
      foreground: "var(--cm-foreground)",
      caret: "#528bff",
      selection: "var(--cm-selection-background)",
      lineHighlight: "#2c313c",
      gutterBackground: "var(--color-background)",
      gutterForeground: "var(--gray-10)",
    },
    styles: [
      { tag: t.comment, color: "var(--cm-comment)" },
      { tag: t.variableName, color: "var(--cm-foreground)" },
      { tag: [t.string, t.special(t.brace)], color: "var(--cm-string)" },
      { tag: t.number, color: "var(--cm-number)" },
      { tag: t.bool, color: "var(--cm-atom)" },
      { tag: t.null, color: "var(--cm-atom)" },
      { tag: t.keyword, color: "var(--cm-keyword)", fontWeight: 500 },
      { tag: t.className, color: "var(--cm-class-name)" },
      { tag: t.definition(t.typeName), color: "var(--cm-class-name)" },
      { tag: t.typeName, color: "var(--cm-type-name)" },
      { tag: t.angleBracket, color: "var(--cm-foreground)" },
      { tag: t.tagName, color: "var(--cm-tag-name)" },
      { tag: t.attributeName, color: "var(--cm-attribute-name)" },
      { tag: t.operator, color: "var(--cm-operator)", fontWeight: 500 },
      { tag: [t.function(t.variableName)], color: "var(--cm-function)" },
      { tag: [t.propertyName], color: "var(--cm-property)" },
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
