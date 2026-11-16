/* Copyright 2026 Marimo. All rights reserved. */

import type {
  EditRequests,
  ExportAsHTMLRequest,
  ExportedFile,
} from "@/core/network/types";
import { assertNever } from "@/utils/assertNever";
import { runServerSidePDFDownload } from "../pdf-export";
import type { ExportFormat, ExportOptions } from "./state";

type ExportRequests = Pick<
  EditRequests,
  | "exportAsHTML"
  | "exportAsMarkdown"
  | "exportAsIPYNB"
  | "exportAsPDF"
  | "exportAsScript"
  | "readCode"
>;

export async function exportNotebook({
  format,
  options,
  requests,
  sourceFilename,
  htmlFiles,
  getLayout,
  captureOutputs,
  capturePNG,
  downloadFile,
}: {
  format: ExportFormat;
  options: ExportOptions;
  requests: ExportRequests;
  sourceFilename: string;
  htmlFiles: string[];
  getLayout: () => Promise<ExportAsHTMLRequest["layout"]>;
  captureOutputs: () => Promise<void>;
  capturePNG: () => Promise<void>;
  downloadFile: (file: ExportedFile) => void;
}): Promise<void> {
  switch (format) {
    case "html": {
      const file = await requests.exportAsHTML({
        download: false,
        files: htmlFiles,
        includeCode: options.html.includeCode,
        layout: await getLayout(),
      });
      downloadFile(file);
      return;
    }
    case "markdown": {
      const file = await requests.exportAsMarkdown({
        download: false,
        flavor: options.markdown.flavor,
      });
      downloadFile(file);
      return;
    }
    case "ipynb": {
      if (options.ipynb.includeOutputs) {
        await captureOutputs();
      }
      const file = await requests.exportAsIPYNB({
        download: false,
        sortMode: options.ipynb.sortMode,
        includeOutputs: options.ipynb.includeOutputs,
      });
      downloadFile(file);
      return;
    }
    case "pdf":
      await runServerSidePDFDownload({
        exportOptions: options.pdf,
        captureOutputs,
        downloadPDF: async (exportOptions) => {
          const file = await requests.exportAsPDF(exportOptions);
          downloadFile(file);
        },
      });
      return;

    case "script": {
      if (options.script.type === "source") {
        const source = await requests.readCode();
        downloadFile({
          contents: source.contents,
          filename: sourceFilename,
          mediaType: "text/plain",
        });
        return;
      }
      const file = await requests.exportAsScript({ download: false });
      downloadFile(file);
      return;
    }
    case "png":
      await capturePNG();
      return;
    default:
      assertNever(format);
  }
}
