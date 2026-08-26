/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { toast } from "@/components/ui/use-toast";
import { downloadByURL } from "@/utils/download";
import {
  buildDownloadAsRequest,
  ExportMenu,
  sourceFormatForCopy,
} from "../export-actions";

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(() => ({ dismiss: vi.fn(), update: vi.fn() })),
}));

vi.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => children,
  TooltipProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/utils/download", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/download")>();
  return { ...actual, downloadByURL: vi.fn() };
});

const PT_BR_LOCALE = { tag: "pt-BR", decimal_separator: "," };

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ExportMenu", () => {
  it("stops a download and shows a standalone export error", async () => {
    const downloadAs = vi.fn().mockResolvedValue({
      url: "",
      filename: "",
      error: "The export locale is invalid.",
    });
    render(
      <TooltipProvider>
        <ExportMenu downloadAs={downloadAs} />
      </TooltipProvider>,
    );

    fireEvent.keyDown(screen.getByTestId("export-button"), {
      key: "ArrowDown",
    });
    fireEvent.click((await screen.findAllByText("CSV"))[0]);

    await waitFor(() => {
      expect(toast).toHaveBeenCalledWith({
        title: "Export failed",
        description: "The export locale is invalid.",
        variant: "danger",
      });
    });
    expect(downloadByURL).not.toHaveBeenCalled();
  });
});

describe("buildDownloadAsRequest", () => {
  it("includes locale for CSV and TSV", () => {
    expect(buildDownloadAsRequest("csv", "pt-BR")).toEqual({
      format: "csv",
      locale: PT_BR_LOCALE,
    });
    expect(buildDownloadAsRequest("tsv", "pt-BR")).toEqual({
      format: "tsv",
      locale: PT_BR_LOCALE,
    });
  });

  it("omits locale for JSON and Parquet", () => {
    expect(buildDownloadAsRequest("json", "pt-BR")).toEqual({ format: "json" });
    expect(buildDownloadAsRequest("parquet", "pt-BR")).toEqual({
      format: "parquet",
    });
  });
});

describe("file and clipboard request parity", () => {
  it("sends the same locale for CSV download and clipboard copy", () => {
    const download = buildDownloadAsRequest("csv", "pt-BR");
    const clipboard = buildDownloadAsRequest(
      sourceFormatForCopy("csv"),
      "pt-BR",
    );
    expect(download).toEqual({ format: "csv", locale: PT_BR_LOCALE });
    expect(clipboard).toEqual(download);
  });

  it("sends the same locale for TSV download and clipboard copy", () => {
    const download = buildDownloadAsRequest("tsv", "pt-BR");
    const clipboard = buildDownloadAsRequest(
      sourceFormatForCopy("tsv"),
      "pt-BR",
    );
    expect(download).toEqual({ format: "tsv", locale: PT_BR_LOCALE });
    expect(clipboard).toEqual(download);
  });

  it("omits locale for JSON, Parquet, and Markdown source requests", () => {
    expect(buildDownloadAsRequest("json", "pt-BR")).toEqual({ format: "json" });
    expect(buildDownloadAsRequest("parquet", "pt-BR")).toEqual({
      format: "parquet",
    });
    expect(
      buildDownloadAsRequest(sourceFormatForCopy("json"), "pt-BR"),
    ).toEqual({ format: "json" });
    expect(
      buildDownloadAsRequest(sourceFormatForCopy("markdown"), "pt-BR"),
    ).toEqual({ format: "json" });
  });
});
