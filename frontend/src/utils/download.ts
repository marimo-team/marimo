/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";
import { toast } from "@/components/ui/use-toast";
import { type CellId, CellOutputId } from "@/core/cells/ids";
import { getRequestClient } from "@/core/network/requests";
import { Filenames } from "@/utils/filenames";
import { Paths } from "@/utils/paths";
import { prettyError } from "./errors";
import { toPng } from "./html-to-image";
import { captureExternalIframes } from "./iframe";
import { Logger } from "./Logger";
import { ProgressState } from "./progress";
import { ToastProgress } from "./toast-progress";

/**
 * Show a loading toast while an async operation is in progress.
 * Automatically dismisses the toast when the operation completes or fails.
 */
export async function withLoadingToast<T>(
  title: string,
  fn: (progress: ProgressState) => Promise<T>,
): Promise<T> {
  const progress = ProgressState.indeterminate();
  const loadingToast = toast({
    title,
    description: React.createElement(ToastProgress, { progress }),
    duration: Infinity,
  });
  try {
    const result = await fn(progress);
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

const THRESHOLD_TIME_MS = 500;
const HIDE_SCROLLBAR_STYLES = `
  * { scrollbar-width: none; -ms-overflow-style: none; }
  *::-webkit-scrollbar { display: none; }
`;

/**
 * Capture a cell output as a PNG data URL.
 *
 * @param cellId - The ID of the cell to capture
 * @returns The PNG as a data URL, or undefined if the cell element wasn't found
 */
export async function getImageDataUrlForCell(
  cellId: CellId,
): Promise<string | undefined> {
  const element = findElementForCell(cellId);
  if (!element) {
    return;
  }

  // TODO: This doesn't handle external iframes + normal elements together (eg. in vstack).
  // It will return the iframe only
  const externalIframeDataUrl = await captureExternalIframes(element);
  if (externalIframeDataUrl) {
    return externalIframeDataUrl;
  }

  const startTime = Date.now();
  const dataUrl = await toPng(element, {
    extraStyleContent: HIDE_SCROLLBAR_STYLES,
    // Add these styles so the element output is not clipped
    // Width can be clipped since pdf has limited width
    style: {
      maxHeight: "none",
      overflow: "visible",
    },
    height: element.scrollHeight,
  });
  const timeTaken = Date.now() - startTime;
  if (timeTaken > THRESHOLD_TIME_MS) {
    Logger.debug(
      "toPng operation for element",
      element,
      `took ${timeTaken} ms (exceeds threshold)`,
    );
  }
  return dataUrl;
}

/**
 * Download a cell output as a PNG image file.
 */
export async function downloadCellOutputAsImage(
  cellId: CellId,
  filename: string,
) {
  try {
    const dataUrl = await getImageDataUrlForCell(cellId);
    if (!dataUrl) {
      throw new Error("Failed to get image data URL");
    }
    downloadByURL(dataUrl, Filenames.toPNG(filename));
  } catch (error) {
    toast({
      title: "Failed to download PNG",
      description: prettyError(error),
      variant: "danger",
    });
  }
}

export const ADD_PRINTING_CLASS = (): (() => void) => {
  document.body.classList.add("printing");
  return () => {
    document.body.classList.remove("printing");
  };
};

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
