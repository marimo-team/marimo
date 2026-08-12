/* Copyright 2026 Marimo. All rights reserved. */

import { atomWithStorage } from "jotai/utils";
import { z } from "zod";
import type { ExportAvailabilityResponse } from "@/core/network/types";
import { adaptForLocalStorage } from "@/utils/storage/jotai";

export const EXPORT_FORMATS = [
  "html",
  "markdown",
  "ipynb",
  "pdf",
  "script",
  "png",
] as const;

export type ExportFormat = (typeof EXPORT_FORMATS)[number];
export type ExportSetupRequirement =
  ExportAvailabilityResponse["formats"][number]["missingSetup"][number];

export const MARKDOWN_FLAVORS = ["pymdown", "qmd", "mystmd", "mdx"] as const;
export const IPYNB_SORT_MODES = ["topological", "top-down"] as const;
export const PDF_PRESETS = ["document", "slides"] as const;
export const SCRIPT_TYPES = ["source", "flat"] as const;

export type MarkdownFlavor = (typeof MARKDOWN_FLAVORS)[number];
export type ScriptType = (typeof SCRIPT_TYPES)[number];

export function isExportFormat(value: unknown): value is ExportFormat {
  return (
    typeof value === "string" &&
    EXPORT_FORMATS.some((format) => format === value)
  );
}

export interface ExportOptions {
  html: {
    includeCode: boolean;
  };
  markdown: {
    flavor: MarkdownFlavor | null;
  };
  ipynb: {
    sortMode: (typeof IPYNB_SORT_MODES)[number];
    includeOutputs: boolean;
  };
  pdf: {
    preset: (typeof PDF_PRESETS)[number];
    includeInputs: boolean;
    includeOutputs: boolean;
    webpdf: boolean;
  };
  script: {
    type: ScriptType;
  };
}

export const DEFAULT_EXPORT_OPTIONS: ExportOptions = {
  html: {
    includeCode: true,
  },
  markdown: {
    flavor: null,
  },
  ipynb: {
    sortMode: "topological",
    includeOutputs: false,
  },
  pdf: {
    preset: "document",
    includeInputs: true,
    includeOutputs: true,
    webpdf: true,
  },
  script: {
    type: "source",
  },
};

function storedValue<Schema extends z.ZodType>(
  schema: Schema,
  fallback: Exclude<z.output<Schema>, undefined>,
) {
  return schema.default(fallback).catch(fallback);
}

function storedGroup<Shape extends z.ZodRawShape>(shape: Shape) {
  return z.object(shape).optional().catch(undefined);
}

const storedExportOptionsSchema = z
  .object({
    html: storedGroup({
      includeCode: storedValue(
        z.boolean(),
        DEFAULT_EXPORT_OPTIONS.html.includeCode,
      ),
    }),
    markdown: storedGroup({
      flavor: storedValue(
        z.enum(MARKDOWN_FLAVORS).nullable(),
        DEFAULT_EXPORT_OPTIONS.markdown.flavor,
      ),
    }),
    ipynb: storedGroup({
      sortMode: storedValue(
        z.enum(IPYNB_SORT_MODES),
        DEFAULT_EXPORT_OPTIONS.ipynb.sortMode,
      ),
      includeOutputs: storedValue(
        z.boolean(),
        DEFAULT_EXPORT_OPTIONS.ipynb.includeOutputs,
      ),
    }),
    pdf: storedGroup({
      preset: storedValue(
        z.enum(PDF_PRESETS),
        DEFAULT_EXPORT_OPTIONS.pdf.preset,
      ),
      includeInputs: storedValue(
        z.boolean(),
        DEFAULT_EXPORT_OPTIONS.pdf.includeInputs,
      ),
      includeOutputs: storedValue(
        z.boolean(),
        DEFAULT_EXPORT_OPTIONS.pdf.includeOutputs,
      ),
      webpdf: storedValue(z.boolean(), DEFAULT_EXPORT_OPTIONS.pdf.webpdf),
    }),
    script: storedGroup({
      type: storedValue(
        z.enum(SCRIPT_TYPES),
        DEFAULT_EXPORT_OPTIONS.script.type,
      ),
    }),
  })
  .catch({});

export type ExportOptionOverrides = {
  [Format in keyof ExportOptions]?: Partial<ExportOptions[Format]>;
};

export function applyExportOptionOverrides(
  options: ExportOptions,
  overrides: ExportOptionOverrides,
): ExportOptions {
  const next = { ...options };
  const mergeFormat = <Format extends keyof ExportOptions>(format: Format) => {
    next[format] = { ...options[format], ...overrides[format] };
  };
  for (const format of Object.keys(overrides) as (keyof ExportOptions)[]) {
    mergeFormat(format);
  }
  return next;
}

export function mergeExportOptions(saved: unknown): ExportOptions {
  return applyExportOptionOverrides(
    DEFAULT_EXPORT_OPTIONS,
    storedExportOptionsSchema.parse(saved),
  );
}

const exportOptionsStorage = adaptForLocalStorage<ExportOptions, unknown>({
  toSerializable: (value) => value,
  fromSerializable: mergeExportOptions,
});

export const exportOptionsAtom = atomWithStorage<ExportOptions>(
  "marimo:export:options:v1",
  DEFAULT_EXPORT_OPTIONS,
  exportOptionsStorage,
  { getOnInit: true },
);

export const lastExportFormatAtom = atomWithStorage<ExportFormat>(
  "marimo:export:last-format:v1",
  "html",
  adaptForLocalStorage<ExportFormat, unknown>({
    toSerializable: (value) => value,
    fromSerializable: (value) => (isExportFormat(value) ? value : "html"),
  }),
  { getOnInit: true },
);

export type ExportBlockReason =
  | { type: "checking-requirements" }
  | { type: "notebook-must-be-named" }
  | { type: "missing-packages"; packages: string[] }
  | { type: "missing-setup"; requirements: ExportSetupRequirement[] }
  | { type: "wasm-runtime" };

export interface ExportFormatStatus {
  available: boolean;
  reason?: ExportBlockReason;
  availabilityCheckFailed?: boolean;
}

interface GetExportFormatStatusOptions {
  format: ExportFormat;
  options: ExportOptions;
  runtime: "server" | "wasm";
  filename: string | null;
  availability:
    | { status: "pending" }
    | { status: "error" }
    | { status: "success"; data: ExportAvailabilityResponse | null };
}

interface ExportFormatRequirements {
  requiresNamedNotebookOnServer: boolean;
  requiresServerRuntime: boolean;
  checksServerAvailability: boolean;
}

const FORMAT_REQUIREMENTS: Record<ExportFormat, ExportFormatRequirements> = {
  html: {
    requiresNamedNotebookOnServer: true,
    requiresServerRuntime: false,
    checksServerAvailability: false,
  },
  markdown: {
    requiresNamedNotebookOnServer: true,
    requiresServerRuntime: false,
    checksServerAvailability: false,
  },
  ipynb: {
    requiresNamedNotebookOnServer: true,
    requiresServerRuntime: true,
    checksServerAvailability: true,
  },
  pdf: {
    requiresNamedNotebookOnServer: true,
    requiresServerRuntime: true,
    checksServerAvailability: true,
  },
  script: {
    requiresNamedNotebookOnServer: false,
    requiresServerRuntime: false,
    checksServerAvailability: false,
  },
  png: {
    requiresNamedNotebookOnServer: false,
    requiresServerRuntime: false,
    checksServerAvailability: false,
  },
};

export function isBrowserPrintExport(
  runtime: "server" | "wasm",
  format: ExportFormat,
): boolean {
  return runtime === "wasm" && format === "pdf";
}

export function getExportFormatStatus({
  format,
  options,
  runtime,
  filename,
  availability,
}: GetExportFormatStatusOptions): ExportFormatStatus {
  const isNotebookSource =
    format === "script" && options.script.type === "source";
  const requirements = isNotebookSource
    ? {
        ...FORMAT_REQUIREMENTS.script,
        requiresNamedNotebookOnServer: true,
      }
    : FORMAT_REQUIREMENTS[format];

  const usesBrowserPrint = isBrowserPrintExport(runtime, format);

  if (runtime === "wasm" && requirements.requiresServerRuntime) {
    return {
      available: usesBrowserPrint,
      reason: { type: "wasm-runtime" },
    };
  }

  if (
    runtime === "server" &&
    requirements.requiresNamedNotebookOnServer &&
    !filename
  ) {
    return {
      available: false,
      reason: { type: "notebook-must-be-named" },
    };
  }

  if (runtime === "wasm" || !requirements.checksServerAvailability) {
    return { available: true };
  }

  if (availability.status === "pending") {
    return {
      available: false,
      reason: { type: "checking-requirements" },
    };
  }

  if (availability.status === "error" || !availability.data) {
    return { available: true, availabilityCheckFailed: true };
  }

  const serverStatus = availability.data.formats.find(
    (candidate) => candidate.format === format,
  );
  if (!serverStatus) {
    return { available: true, availabilityCheckFailed: true };
  }
  if (!serverStatus.dependenciesAvailable) {
    if (serverStatus.missingPackages.length > 0) {
      return {
        available: false,
        reason: {
          type: "missing-packages",
          packages: serverStatus.missingPackages,
        },
      };
    }
    if (serverStatus.missingSetup.length > 0) {
      return {
        available: false,
        reason: {
          type: "missing-setup",
          requirements: serverStatus.missingSetup,
        },
      };
    }
    return {
      available: true,
      availabilityCheckFailed: true,
    };
  }

  return { available: true };
}
