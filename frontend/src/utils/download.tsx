/* Copyright 2026 Marimo. All rights reserved. */
import { toPng } from "html-to-image";
import { Spinner } from "@/components/icons/spinner";
import { toast } from "@/components/ui/use-toast";
import { getRequestClient } from "@/core/network/requests";
import { Filenames } from "@/utils/filenames";
import { Paths } from "@/utils/paths";

/**
 * Show a loading toast while an async operation is in progress.
 * Automatically dismisses the toast when the operation completes or fails.
 */
export async function withLoadingToast<T>(
  title: string,
  fn: () => Promise<T>,
): Promise<T> {
  const loadingToast = toast({
    title,
    description: <Spinner size="small" />,
  });
  try {
    const result = await fn();
    loadingToast.dismiss();
    return result;
  } catch (error) {
    loadingToast.dismiss();
    throw error;
  }
}

export async function downloadHTMLAsImage(
  element: HTMLElement,
  filename: string,
) {
  // Capture current scroll position
  const appEl = document.getElementById("App");
  const currentScrollY = appEl?.scrollTop ?? 0;
  // Add classnames for printing
  document.body.classList.add("printing");
  try {
    // Get screenshot
    const dataUrl = await toPng(element);
    downloadByURL(dataUrl, Filenames.toPNG(filename));
  } catch {
    toast({
      title: "Error",
      description: "Failed to download as PNG.",
      variant: "danger",
    });
  } finally {
    // Remove classnames for printing
    document.body.classList.remove("printing");
    // Restore scroll position
    requestAnimationFrame(() => {
      appEl?.scrollTo(0, currentScrollY);
    });
  }
}

export function downloadByURL(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  a.remove();
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  downloadByURL(url, filename);
  URL.revokeObjectURL(url);
}

/**
 * Download the current notebook as a PDF file.
 *
 * We prefer to use webpdf mode, which only requires Chromium to be installed.
 * Standard PDF requires Pandoc & TeX (~few GBs).
 */
export async function downloadAsPDF(opts: {
  filename: string;
  webpdf: boolean;
}) {
  const client = getRequestClient();
  const { filename, webpdf } = opts;

  const pdfBlob = await client.exportAsPDF({
    webpdf: webpdf,
  });

  const filenameWithoutPath = Paths.basename(filename) ?? "notebook.py";
  downloadBlob(pdfBlob, Filenames.toPDF(filenameWithoutPath));
}
