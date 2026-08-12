/* Copyright 2026 Marimo. All rights reserved. */

import {
  MARKDOWN_EXTENSIONS,
  MARKDOWN_SUFFIXES,
} from "@/core/network/markdown-export";
import { Filenames } from "@/utils/filenames";
import { shellQuote } from "@/utils/shell";
import type { ExportFormat, ExportOptions, MarkdownFlavor } from "./state";

function inferMarkdownFlavor(filename: string): MarkdownFlavor {
  if (filename.endsWith(".myst.md")) {
    return "mystmd";
  }
  if (filename.endsWith(".qmd")) {
    return "qmd";
  }
  if (filename.endsWith(".mdx")) {
    return "mdx";
  }
  return "pymdown";
}

function markdownOutputFilename(
  filename: string,
  selectedFlavor: MarkdownFlavor | null,
): string {
  const flavor = selectedFlavor ?? inferMarkdownFlavor(filename);
  const extension = MARKDOWN_EXTENSIONS[flavor];
  const suffix = MARKDOWN_SUFFIXES.find((candidate) =>
    filename.endsWith(candidate),
  );
  let stem = Filenames.withoutExtension(filename);
  if (suffix) {
    stem = filename.slice(0, -suffix.length);
  }
  const output = `${stem}.${extension}`;
  if (output !== filename) {
    return output;
  }
  return `${filename.slice(0, -(extension.length + 1))}.export.${extension}`;
}

type FlagValue = boolean | string | null;

function translateFlags(values: Record<string, FlagValue>): string[] {
  return Object.entries(values).flatMap(([name, value]) => {
    if (value === null) {
      return [];
    }
    if (value === true) {
      return [`--${name}`];
    }
    if (value === false) {
      return [`--no-${name}`];
    }
    return [`--${name}=${value}`];
  });
}

function webPDFFlagValue(pdf: ExportOptions["pdf"]): boolean | null {
  if (pdf.preset === "document") {
    return pdf.webpdf;
  }
  return null;
}

type CommandFormat = Exclude<ExportFormat, "png">;

interface ExportCommandDefinition {
  subcommand: string;
  flags: (options: ExportOptions) => Record<string, FlagValue>;
  outputFilename: (source: string, options: ExportOptions) => string;
}

const EXPORT_COMMAND_DEFINITIONS: Record<
  CommandFormat,
  ExportCommandDefinition
> = {
  html: {
    subcommand: "html",
    flags: ({ html }) => ({ "include-code": html.includeCode }),
    outputFilename: (source) => Filenames.toHTML(source),
  },
  markdown: {
    subcommand: "md",
    flags: ({ markdown }) => ({ flavor: markdown.flavor }),
    outputFilename: (source, { markdown }) =>
      markdownOutputFilename(source, markdown.flavor),
  },
  ipynb: {
    subcommand: "ipynb",
    flags: ({ ipynb }) => ({
      sort: ipynb.sortMode,
      "include-outputs": ipynb.includeOutputs,
    }),
    outputFilename: (source) => Filenames.toIPYNB(source),
  },
  pdf: {
    subcommand: "pdf",
    flags: ({ pdf }) => ({
      as: pdf.preset,
      "include-inputs": pdf.includeInputs,
      "include-outputs": pdf.includeOutputs,
      webpdf: webPDFFlagValue(pdf),
    }),
    outputFilename: (source) => Filenames.toPDF(source),
  },
  script: {
    subcommand: "script",
    flags: () => ({}),
    outputFilename: (source) =>
      `${Filenames.withoutExtension(source)}.script.py`,
  },
};

export function getExportCommand({
  format,
  filename,
  options,
}: {
  format: ExportFormat;
  filename: string | null;
  options: ExportOptions;
}): string | null {
  if (
    format === "png" ||
    (format === "script" && options.script.type === "source") ||
    !filename
  ) {
    return null;
  }

  const definition = EXPORT_COMMAND_DEFINITIONS[format];
  return [
    "marimo",
    "export",
    definition.subcommand,
    shellQuote(filename),
    ...translateFlags(definition.flags(options)),
    "-o",
    shellQuote(definition.outputFilename(filename, options)),
  ].join(" ");
}
