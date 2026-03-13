/* Copyright 2026 Marimo. All rights reserved. */

type Preset = "document" | "slides";
type DownloadPDF = (opts: {
  filename: string;
  webpdf: boolean;
  preset: Preset;
  includeInputs: boolean;
  rasterServer: "live" | "static";
}) => Promise<void>;

export async function runServerSidePDFDownload(opts: {
  filename: string;
  preset: Preset;
  downloadPDF: DownloadPDF;
}): Promise<void> {
  const { filename, preset, downloadPDF } = opts;

  await downloadPDF({
    filename,
    webpdf: true,
    preset,
    includeInputs: false,
    rasterServer: "live",
  });
}
