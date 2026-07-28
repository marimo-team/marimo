/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it, vi } from "vitest";
import { runServerSidePDFDownload } from "../pdf-export";

describe("runServerSidePDFDownload", () => {
  it("downloads document preset via backend PDF endpoint", async () => {
    const downloadPDF = vi.fn().mockResolvedValue(undefined);

    await runServerSidePDFDownload({
      preset: "document",
      downloadPDF,
    });

    expect(downloadPDF).toHaveBeenCalledWith({
      webpdf: false,
      preset: "document",
      includeInputs: true,
      rasterServer: "static",
    });
  });

  it("downloads slides preset via backend PDF endpoint", async () => {
    const downloadPDF = vi.fn().mockResolvedValue(undefined);

    await runServerSidePDFDownload({
      preset: "slides",
      downloadPDF,
    });

    expect(downloadPDF).toHaveBeenCalledWith({
      webpdf: false,
      preset: "slides",
      includeInputs: true,
      rasterServer: "static",
    });
  });
});
