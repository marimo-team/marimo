/* Copyright 2026 Marimo. All rights reserved. */

import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { Filenames } from "@/utils/filenames";
import { Paths } from "@/utils/paths";
import {
  DEFAULT_MARKDOWN_FLAVOR,
  MARKDOWN_EXTENSIONS,
} from "./markdown-export";
import type { ExportAsMarkdownRequest } from "./types";

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
  const extension = MARKDOWN_EXTENSIONS[flavor ?? DEFAULT_MARKDOWN_FLAVOR];
  return getDefaultExportFilename(extension);
}
