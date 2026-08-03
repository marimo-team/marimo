/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { ExportAvailabilityResponse } from "@/core/network/types";
import {
  applyExportOptionOverrides,
  DEFAULT_EXPORT_OPTIONS,
  type ExportFormat,
  type ExportOptions,
  getExportFormatStatus,
  isExportFormat,
  mergeExportOptions,
} from "../state";

const AVAILABLE: ExportAvailabilityResponse = {
  source: "server",
  formats: [
    {
      format: "ipynb",
      dependenciesAvailable: true,
      missingPackages: [],
    },
    {
      format: "pdf",
      dependenciesAvailable: true,
      missingPackages: [],
    },
  ],
};

const EXPECTED_DEFAULT_OPTIONS: ExportOptions = {
  html: { includeCode: true },
  markdown: { flavor: null },
  ipynb: { sortMode: "topological", includeOutputs: false },
  pdf: {
    preset: "document",
    includeInputs: true,
    includeOutputs: true,
    webpdf: true,
  },
  script: { type: "source" },
};

type StatusOptions = Parameters<typeof getExportFormatStatus>[0];

function status(
  format: ExportFormat,
  overrides: Partial<Omit<StatusOptions, "format">> = {},
) {
  return getExportFormatStatus({
    format,
    options: DEFAULT_EXPORT_OPTIONS,
    runtime: "server",
    filename: "notebook.py",
    availability: { status: "success", data: AVAILABLE },
    ...overrides,
  });
}

describe("export option state", () => {
  it("adds current defaults to a stored partial option shape", () => {
    expect(
      mergeExportOptions({
        html: { includeCode: false },
        pdf: { preset: "slides" },
      }),
    ).toEqual({
      ...EXPECTED_DEFAULT_OPTIONS,
      html: { includeCode: false },
      pdf: {
        ...EXPECTED_DEFAULT_OPTIONS.pdf,
        preset: "slides",
      },
    });
  });

  it("keeps valid stored fields and resets invalid fields", () => {
    expect(
      mergeExportOptions({
        html: { includeCode: "false" },
        markdown: { flavor: "unknown" },
        ipynb: { sortMode: "unknown", includeOutputs: true },
        pdf: {
          preset: "unknown",
          includeInputs: false,
          includeOutputs: "false",
          webpdf: false,
        },
        script: { type: "unknown" },
      }),
    ).toEqual({
      ...EXPECTED_DEFAULT_OPTIONS,
      ipynb: {
        ...EXPECTED_DEFAULT_OPTIONS.ipynb,
        includeOutputs: true,
      },
      pdf: {
        ...EXPECTED_DEFAULT_OPTIONS.pdf,
        includeInputs: false,
        webpdf: false,
      },
    });
  });

  it.each([null, { pdf: "invalid" }])(
    "resets malformed stored options",
    (stored) => {
      expect(mergeExportOptions(stored)).toEqual(EXPECTED_DEFAULT_OPTIONS);
    },
  );

  it("applies a shortcut preset without resetting sibling options", () => {
    const options = {
      ...DEFAULT_EXPORT_OPTIONS,
      pdf: {
        preset: "document" as const,
        includeInputs: false,
        includeOutputs: false,
        webpdf: false,
      },
    };

    expect(
      applyExportOptionOverrides(options, {
        pdf: { preset: "slides" },
      }).pdf,
    ).toEqual({
      ...options.pdf,
      preset: "slides",
    });
    expect(
      applyExportOptionOverrides(options, {
        script: { type: "flat" },
      }).script,
    ).toEqual({ type: "flat" });
  });

  it("accepts current formats and rejects unknown values", () => {
    expect(isExportFormat("markdown")).toBe(true);
    expect(isExportFormat("wasm")).toBe(false);
    expect(isExportFormat(null)).toBe(false);
  });
});

describe("getExportFormatStatus", () => {
  it("waits only for formats with server dependencies", () => {
    expect(status("ipynb", { availability: { status: "pending" } })).toEqual({
      available: false,
      reason: { type: "checking-requirements" },
    });
    expect(status("html", { availability: { status: "pending" } })).toEqual({
      available: true,
    });
  });

  it("requires a notebook name for file-backed server formats", () => {
    expect(status("markdown", { filename: null })).toEqual({
      available: false,
      reason: { type: "notebook-must-be-named" },
    });
  });

  it("requires a saved file for notebook source but not flat script", () => {
    expect(status("script", { filename: null })).toEqual({
      available: false,
      reason: { type: "notebook-must-be-named" },
    });
    expect(
      status("script", {
        filename: null,
        options: {
          ...DEFAULT_EXPORT_OPTIONS,
          script: { type: "flat" },
        },
      }),
    ).toEqual({ available: true });
  });

  it("reports missing server packages", () => {
    expect(
      status("pdf", {
        availability: {
          status: "success",
          data: {
            source: "server",
            formats: [
              {
                format: "pdf",
                dependenciesAvailable: false,
                missingPackages: ["nbconvert[webpdf]"],
              },
            ],
          },
        },
      }),
    ).toEqual({
      available: false,
      reason: {
        type: "missing-packages",
        packages: ["nbconvert[webpdf]"],
      },
    });
  });

  it.each([
    ["html", true, undefined],
    ["markdown", true, undefined],
    ["ipynb", false, "wasm-runtime"],
    ["pdf", true, "wasm-runtime"],
    ["script", true, undefined],
    ["png", true, undefined],
  ] as const)(
    "describes %s availability in WebAssembly",
    (format, available, reason) => {
      expect(
        status(format, {
          runtime: "wasm",
          filename: null,
          availability: { status: "success", data: null },
        }),
      ).toEqual({
        available,
        ...(reason ? { reason: { type: reason } } : {}),
      });
    },
  );

  it("allows an export attempt when the availability check fails", () => {
    expect(status("pdf", { availability: { status: "error" } })).toEqual({
      available: true,
      availabilityCheckFailed: true,
    });
  });
});
