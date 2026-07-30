/* Copyright 2026 Marimo. All rights reserved. */

type Preset = "document" | "slides";
interface PDFExportOptions {
  webpdf: boolean;
  preset: Preset;
  includeInputs: boolean;
  includeOutputs: boolean;
}
type DownloadPDF = (opts: PDFExportOptions) => Promise<void>;

export async function runServerSidePDFDownload(opts: {
  exportOptions: PDFExportOptions;
  captureOutputs: () => Promise<void>;
  downloadPDF: DownloadPDF;
}): Promise<void> {
  const { exportOptions, captureOutputs, downloadPDF } = opts;

  if (exportOptions.includeOutputs) {
    await captureOutputs();
  }
  await downloadPDF(exportOptions);
}
