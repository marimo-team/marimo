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
      webpdf: false,
      preset: "document",
      includeInputs: true,
      rasterServer: "static",
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
      webpdf: false,
      preset: "slides",
      includeInputs: true,
      rasterServer: "static",
    });
  });
});
