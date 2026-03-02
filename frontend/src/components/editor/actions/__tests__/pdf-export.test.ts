/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { runServerSidePDFDownload } from "../pdf-export";

describe("runServerSidePDFDownload", () => {
  it("downloads document preset via backend PDF endpoint", async () => {
    const downloadPDF = vi.fn().mockResolvedValue(undefined);

    await runServerSidePDFDownload({
      filename: "slides.py",
      preset: "document",
      downloadPDF,
    });

    expect(downloadPDF).toHaveBeenCalledWith({
      filename: "slides.py",
      webpdf: true,
      preset: "document",
      includeInputs: false,
      rasterServer: "live",
    });
  });

  it("downloads slides preset via backend PDF endpoint", async () => {
    const downloadPDF = vi.fn().mockResolvedValue(undefined);

    await runServerSidePDFDownload({
      filename: "slides.py",
      preset: "slides",
      downloadPDF,
    });

    expect(downloadPDF).toHaveBeenCalledWith({
      filename: "slides.py",
      webpdf: true,
      preset: "slides",
      includeInputs: false,
      rasterServer: "live",
    });
  });
});
