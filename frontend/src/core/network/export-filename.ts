/* Copyright 2026 Marimo. All rights reserved. */

import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { Filenames } from "@/utils/filenames";
import { Paths } from "@/utils/paths";
import type { ExportAsMarkdownRequest, MarkdownExportFlavor } from "./types";

const MARKDOWN_EXTENSIONS = {
  pymdown: "md",
  qmd: "qmd",
  mystmd: "myst.md",
  mdx: "mdx",
} satisfies Record<MarkdownExportFlavor, string>;
const DEFAULT_MARKDOWN_EXTENSION: MarkdownExportFlavor = "pymdown";

const DEFAULT_EXPORT_FILENAME = "download";

function getNotebookStem(): string | undefined {
  const filename = store.get(filenameAtom);
  if (!filename) {
    return undefined;
  }
  const basename = Paths.basename(filename);
  return Filenames.withoutExtension(basename);
}

export function getDefaultExportFilename(extension: string): string {
  const stem = getNotebookStem();
  if (stem) {
    return `${stem}.${extension}`;
  }
  return `${DEFAULT_EXPORT_FILENAME}.${extension}`;
}

export function getDefaultMarkdownExportFilename(
  flavor: ExportAsMarkdownRequest["flavor"],
): string {
  const extension = MARKDOWN_EXTENSIONS[flavor ?? DEFAULT_MARKDOWN_EXTENSION];
  return getDefaultExportFilename(extension);
}
