/* Copyright 2026 Marimo. All rights reserved. */

import type { MarkdownExportFlavor } from "./types";

export const MARKDOWN_EXTENSIONS = {
  pymdown: "md",
  qmd: "qmd",
  mystmd: "myst.md",
  mdx: "mdx",
} satisfies Record<MarkdownExportFlavor, string>;
export const MARKDOWN_SUFFIXES = [
  ".myst.md",
  ".markdown",
  ".qmd",
  ".mdx",
  ".md",
];

export const DEFAULT_MARKDOWN_FLAVOR: MarkdownExportFlavor = "pymdown";
