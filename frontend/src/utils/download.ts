/* Copyright 2026 Marimo. All rights reserved. */

import { toast } from "@/components/ui/use-toast";
import { type CellId, CellOutputId } from "@/core/cells/ids";
import { getRequestClient } from "@/core/network/requests";
import { Filenames } from "@/utils/filenames";
import { Paths } from "@/utils/paths";
import { prettyError } from "./errors";
import { toPng } from "./html-to-image";
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

/**
 * Reference counter for body.printing class to handle concurrent screenshot captures.
 * Only adds the class when count goes 0→1, only removes when count goes 1→0.
 */
let bodyPrintingRefCount = 0;

function acquireBodyPrinting() {
  bodyPrintingRefCount++;
  if (bodyPrintingRefCount === 1) {
    document.body.classList.add("printing");
  }
}

function releaseBodyPrinting() {
  bodyPrintingRefCount--;
  if (bodyPrintingRefCount === 0) {
    document.body.classList.remove("printing");
  }
}

/**
 * Prepare a cell element for screenshot capture.
 *
 * @param element - The cell output element to prepare
 * @param enablePrintMode - When true, adds a 'printing' class to the body.
 *   This can cause layout shifts that cause the page to scroll.
 * @returns A cleanup function to restore the element's original state
 */
function prepareCellElementForScreenshot(
  element: HTMLElement,
  enablePrintMode: boolean,
) {
  element.classList.add("printing-output");
  if (enablePrintMode) {
    acquireBodyPrinting();
  }
  const originalOverflow = element.style.overflow;
  element.style.overflow = "auto";

  return () => {
    element.classList.remove("printing-output");
    if (enablePrintMode) {
      releaseBodyPrinting();
    }
    element.style.overflow = originalOverflow;
  };
}

/**
 * Capture a cell output as a PNG data URL.
 *
 * @param cellId - The ID of the cell to capture
 * @param enablePrintMode - When true, enables print mode which adds a 'printing' class to the body.
 *   This can cause layout shifts that cause the page to scroll.
 * @returns The PNG as a data URL, or undefined if the cell element wasn't found
 */
export async function getImageDataUrlForCell(
  cellId: CellId,
  enablePrintMode = true,
): Promise<string | undefined> {
  const element = findElementForCell(cellId);
  if (!element) {
    return;
  }
  const cleanup = prepareCellElementForScreenshot(element, enablePrintMode);

  try {
    return await toPng(element);
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
    prepare: () => prepareCellElementForScreenshot(element, true),
  });
}

export async function downloadHTMLAsImage(opts: {
  element: HTMLElement;
  filename: string;
  prepare?: (element: HTMLElement) => () => void;
}) {
  const { element, filename, prepare } = opts;

  // Capture current scroll position
  const appEl = document.getElementById("App");
  const currentScrollY = appEl?.scrollTop ?? 0;

  let cleanup: (() => void) | undefined;
  if (prepare) {
    cleanup = prepare(element);
  } else {
    // When no prepare function is provided (e.g., downloading full notebook),
    // add body.printing ourselves
    document.body.classList.add("printing");
  }

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
