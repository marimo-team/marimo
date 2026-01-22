/* Copyright 2026 Marimo. All rights reserved. */
import { toPng } from "html-to-image";
import { toast } from "@/components/ui/use-toast";
import { type CellId, CellOutputId } from "@/core/cells/ids";
import { getRequestClient } from "@/core/network/requests";
import { Filenames } from "@/utils/filenames";
import { Paths } from "@/utils/paths";
import { prettyError } from "./errors";
import { Logger } from "./Logger";

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
    duration: Infinity,
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

function findElementForCell(cellId: CellId): HTMLElement | undefined {
  const element = document.getElementById(CellOutputId.create(cellId));
  if (!element) {
    Logger.error(`Output element not found for cell ${cellId}`);
    return;
  }
  return element;
}

/*
 * Prepare a cell element for screenshot capture.
 * Returns a cleanup function that should be called when the screenshot is complete.
 */
function prepareCellElementForScreenshot(element: HTMLElement) {
  element.classList.add("printing-output");
  document.body.classList.add("printing");
  const originalOverflow = element.style.overflow;
  element.style.overflow = "auto";

  return () => {
    element.classList.remove("printing-output");
    document.body.classList.remove("printing");
    element.style.overflow = originalOverflow;
  };
}

/**
 * Capture a cell output as a PNG data URL.
 */
export async function getImageDataUrlForCell(
  cellId: CellId,
): Promise<string | undefined> {
  const element = findElementForCell(cellId);
  if (!element) {
    return;
  }
  const cleanup = prepareCellElementForScreenshot(element);

  try {
    return await toPng(element);
  } catch {
    Logger.error("Failed to capture element as PNG.");
    return;
  } finally {
    cleanup();
  }
}

/**
 * Download a cell output as a PNG image file.
 */
export async function downloadCellOutputAsImage(
  cellId: CellId,
  filename: string,
) {
  const element = findElementForCell(cellId);
  if (!element) {
    return;
  }

  await downloadHTMLAsImage({
    element,
    filename,
    prepare: prepareCellElementForScreenshot,
  });
}

export async function downloadHTMLAsImage(opts: {
  element: HTMLElement;
  filename: string;
  prepare?: (element: HTMLElement) => () => void;
}) {
  const { element, filename, prepare } = opts;
  let cleanup: (() => void) | undefined;
  if (prepare) {
    cleanup = prepare(element);
  }
  // Typically used for downloading the entire notebook
  document.body.classList.add("printing");

  // Capture current scroll position
  const appEl = document.getElementById("App");
  const currentScrollY = appEl?.scrollTop ?? 0;
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
    cleanup?.();
    if (document.body.classList.contains("printing")) {
      document.body.classList.remove("printing");
    }
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
 * WebPDF only requires Chromium to be installed.
 * Standard PDF requires Pandoc & TeX (~few GBs) but is of higher quality.
 */
export async function downloadAsPDF(opts: {
  filename: string;
  webpdf: boolean;
}) {
  const client = getRequestClient();
  const { filename, webpdf } = opts;

  try {
    const pdfBlob = await client.exportAsPDF({
      webpdf,
    });

    const filenameWithoutPath = Paths.basename(filename);
    downloadBlob(pdfBlob, Filenames.toPDF(filenameWithoutPath));
  } catch (error) {
    toast({
      title: "Failed to download",
      description: prettyError(error),
      variant: "danger",
    });
    throw error;
  }
}
