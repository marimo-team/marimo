/* Copyright 2026 Marimo. All rights reserved. */

type Preset = "document" | "slides";
type DownloadPDF = (opts: {
  webpdf: boolean;
  preset: Preset;
  includeInputs: boolean;
  rasterServer: "live" | "static";
}) => Promise<void>;

export async function runServerSidePDFDownload(opts: {
  preset: Preset;
  downloadPDF: DownloadPDF;
}): Promise<void> {
  const { preset, downloadPDF } = opts;

  await downloadPDF({
    webpdf: false,
    preset,
    includeInputs: true,
    rasterServer: "static",
  });
}
