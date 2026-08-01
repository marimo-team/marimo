/* Copyright 2026 Marimo. All rights reserved. */

import { assertNever } from "@/utils/assertNever";
import { Filenames } from "@/utils/filenames";
import { shellQuote } from "@/utils/shell";
import type { ExportFormat, ExportOptions, MarkdownFlavor } from "./state";

const MARKDOWN_EXTENSIONS: Record<MarkdownFlavor, string> = {
  pymdown: "md",
  qmd: "qmd",
  mystmd: "myst.md",
  mdx: "mdx",
};

const MARKDOWN_SUFFIXES = [".myst.md", ".markdown", ".qmd", ".mdx", ".md"];

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
  const output = suffix
    ? `${filename.slice(0, -suffix.length)}.${extension}`
    : `${Filenames.withoutExtension(filename)}.${extension}`;
  if (output !== filename) {
    return output;
  }
  return `${filename.slice(0, -(extension.length + 1))}.export.${extension}`;
}

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

  const source = filename;
  const quotedSource = shellQuote(source);

  switch (format) {
    case "html": {
      const output = Filenames.toHTML(source);
      const includeCode = options.html.includeCode
        ? "--include-code"
        : "--no-include-code";
      return `marimo export html ${quotedSource} ${includeCode} -o ${shellQuote(output)}`;
    }
    case "markdown": {
      const flavor = options.markdown.flavor;
      const flavorFlag = flavor ? ` --flavor=${flavor}` : "";
      const output = markdownOutputFilename(source, flavor);
      return `marimo export md ${quotedSource}${flavorFlag} -o ${shellQuote(output)}`;
    }
    case "ipynb": {
      const includeOutputs = options.ipynb.includeOutputs
        ? "--include-outputs"
        : "--no-include-outputs";
      const output = Filenames.toIPYNB(source);
      return `marimo export ipynb ${quotedSource} --sort=${options.ipynb.sortMode} ${includeOutputs} -o ${shellQuote(output)}`;
    }
    case "pdf": {
      const includeInputs = options.pdf.includeInputs
        ? "--include-inputs"
        : "--no-include-inputs";
      const includeOutputs = options.pdf.includeOutputs
        ? "--include-outputs"
        : "--no-include-outputs";
      const webpdf = options.pdf.webpdf ? "--webpdf" : "--no-webpdf";
      const webpdfFlag = options.pdf.preset === "document" ? ` ${webpdf}` : "";
      const output = Filenames.toPDF(source);
      return `marimo export pdf ${quotedSource} --as=${options.pdf.preset} ${includeInputs} ${includeOutputs}${webpdfFlag} -o ${shellQuote(output)}`;
    }
    case "script": {
      const output = `${Filenames.withoutExtension(source)}.script.py`;
      return `marimo export script ${quotedSource} -o ${shellQuote(output)}`;
    }
    default:
      return assertNever(format);
  }
}
