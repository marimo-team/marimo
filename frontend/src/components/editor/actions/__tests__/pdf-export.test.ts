/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { runServerSidePDFDownload } from "../pdf-export";

describe("runServerSidePDFDownload", () => {
  it("captures current outputs before downloading the PDF", async () => {
    const calls: string[] = [];
    const captureOutputs = vi.fn(async () => {
      calls.push("capture:start");
      await Promise.resolve();
      calls.push("capture:end");
    });
    const downloadPDF = vi.fn(async () => {
      calls.push("download");
    });

    await runServerSidePDFDownload({
      exportOptions: {
        webpdf: false,
        preset: "document",
        includeInputs: true,
        includeOutputs: true,
      },
      captureOutputs,
      downloadPDF,
    });

    expect(calls).toEqual(["capture:start", "capture:end", "download"]);
    expect(downloadPDF).toHaveBeenCalledWith({
      webpdf: false,
      preset: "document",
      includeInputs: true,
      includeOutputs: true,
    });
  });

  it("skips browser capture when outputs are excluded", async () => {
    const captureOutputs = vi.fn().mockResolvedValue(undefined);
    const downloadPDF = vi.fn().mockResolvedValue(undefined);

    await runServerSidePDFDownload({
      exportOptions: {
        webpdf: true,
        preset: "slides",
        includeInputs: false,
        includeOutputs: false,
      },
      captureOutputs,
      downloadPDF,
    });

    expect(captureOutputs).not.toHaveBeenCalled();
    expect(downloadPDF).toHaveBeenCalledWith({
      webpdf: true,
      preset: "slides",
      includeInputs: false,
      includeOutputs: false,
    });
  });
});
