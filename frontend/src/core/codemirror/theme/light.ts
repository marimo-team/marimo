/* Copyright 2024 Marimo. All rights reserved. */
import { createTheme } from "thememirror";
import { tags as t } from "@lezer/highlight";

export const lightTheme = createTheme({
  variant: "light",
  settings: {
    background: "#ffffff",
    foreground: "#000000",
    caret: "#000000",
    selection: "#d7d4f0",
    lineHighlight: "#f7f7f7",
    gutterBackground: "var(--color-background)",
    gutterForeground: "var(--gray-10)",
  },
  styles: [
    // Default codemirror light theme
    { tag: t.comment, color: "#708090" },
    { tag: t.variableName, color: "#000000" },
    { tag: [t.string, t.special(t.brace)], color: "#a11" },
    { tag: t.number, color: "#164" },
    { tag: t.bool, color: "#219" },
    { tag: t.null, color: "#219" },
    { tag: t.keyword, color: "#708", fontWeight: 500 },
    // { tag: t.operator, color: '#000' },
    { tag: t.className, color: "#00f" },
    { tag: t.definition(t.typeName), color: "#00f" },
    { tag: t.typeName, color: "#085" },
    { tag: t.angleBracket, color: "#000000" },
    { tag: t.tagName, color: "#170" },
    { tag: t.attributeName, color: "#00c" },
    // Adjustments
    { tag: t.operator, color: "#a2f", fontWeight: 500 },
    {
      tag: [t.function(t.variableName)],
      color: "#00c",
    },
    {
      tag: [t.propertyName],
      color: "#05a",
    },
  ],
});
