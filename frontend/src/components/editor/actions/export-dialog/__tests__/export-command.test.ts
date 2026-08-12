/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import { getExportCommand } from "../export-command";
import {
  DEFAULT_EXPORT_OPTIONS,
  type ExportFormat,
  type ExportOptions,
} from "../state";

function options(overrides: Partial<ExportOptions> = {}): ExportOptions {
  return {
    ...DEFAULT_EXPORT_OPTIONS,
    ...overrides,
  };
}

function command(
  format: ExportFormat,
  filename: string | null,
  overrides: Partial<ExportOptions> = {},
) {
  return getExportCommand({ format, filename, options: options(overrides) });
}

describe("getExportCommand", () => {
  it("includes the selected HTML code setting and derived output path", () => {
    expect(
      command("html", "/tmp/my notebook.py", {
        html: { includeCode: false },
      }),
    ).toBe(
      "marimo export html '/tmp/my notebook.py' --no-include-code -o '/tmp/my notebook.html'",
    );
  });

  it("uses the selected Markdown flavor and its extension", () => {
    expect(
      command("markdown", "report.py", {
        markdown: { flavor: "mystmd" },
      }),
    ).toBe("marimo export md report.py --flavor=mystmd -o report.myst.md");
  });

  it.each([
    ["report.md", "report.export.md"],
    ["report.markdown", "report.md"],
    ["report.qmd", "report.export.qmd"],
    ["report.myst.md", "report.export.myst.md"],
    ["report.mdx", "report.export.mdx"],
  ])(
    "keeps the automatic Markdown output distinct from %s",
    (filename, output) => {
      expect(command("markdown", filename)).toBe(
        `marimo export md ${filename} -o ${output}`,
      );
    },
  );

  it("includes every configurable document PDF setting", () => {
    expect(
      command("pdf", "report.py", {
        pdf: {
          preset: "document",
          includeInputs: false,
          includeOutputs: false,
          webpdf: false,
        },
      }),
    ).toBe(
      "marimo export pdf report.py --as=document --no-include-inputs --no-include-outputs --no-webpdf -o report.pdf",
    );
  });

  it("includes IPYNB cell order and output selection", () => {
    expect(
      command("ipynb", "report.py", {
        ipynb: { sortMode: "top-down", includeOutputs: true },
      }),
    ).toBe(
      "marimo export ipynb report.py --sort=top-down --include-outputs -o report.ipynb",
    );
  });

  it("omits the fixed WebPDF engine flag for slide PDFs", () => {
    expect(
      command("pdf", "slides.py", {
        pdf: {
          preset: "slides",
          includeInputs: false,
          includeOutputs: false,
          webpdf: false,
        },
      }),
    ).toBe(
      "marimo export pdf slides.py --as=slides --no-include-inputs --no-include-outputs -o slides.pdf",
    );
  });

  it("uses the script export filename contract", () => {
    expect(
      command("script", "analysis.py", {
        script: { type: "flat" },
      }),
    ).toBe("marimo export script analysis.py -o analysis.script.py");
  });

  it.each([
    ["editable notebook source", "script", "analysis.py"],
    ["unnamed notebook", "html", null],
    ["PNG capture", "png", "analysis.py"],
  ] as const)("has no command for %s", (_case, format, filename) => {
    expect(command(format, filename)).toBeNull();
  });
});
