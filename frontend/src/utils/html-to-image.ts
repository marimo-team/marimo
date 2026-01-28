/* Copyright 2026 Marimo. All rights reserved. */
import { getFontEmbedCSS, toPng as htmlToImageToPng } from "html-to-image";
import {
  createContext,
  destroyContext,
  domToPng as modernScreenshotToPng,
} from "modern-screenshot";
import workerUrl from "modern-screenshot/worker?url";
import { Logger } from "./Logger";

export type HtmlToImageOptions = Parameters<typeof htmlToImageToPng>[1];

/**
 * Filter function for both libraries - compatible with Node type.
 */
function defaultFilter(node: Node): boolean {
  try {
    if ("classList" in node) {
      const element = node as Element;
      // Filter out matplotlib toolbars
      return !element.classList.contains("mpl-toolbar");
    }
    return true;
  } catch (error) {
    Logger.error("Error filtering node:", error);
    return true;
  }
}

/**
 * Default options for html-to-image conversions.
 * These handle common edge cases like filtering out toolbars and logging errors.
 */
export const defaultHtmlToImageOptions: HtmlToImageOptions = {
  filter: defaultFilter,
  onImageErrorHandler: (event) => {
    Logger.error("Error loading image:", event);
  },
};

/**
 * Convert an HTML element to a PNG data URL.
 * This is a wrapper around html-to-image's toPng with default options applied.
 */
export function toPng(
  element: HTMLElement,
  options?: HtmlToImageOptions,
): Promise<string> {
  Logger.warn("toPng called");
  return toPngComparison(element, options).then((result) => {
    return result.modernScreenshotWorker.dataUrl;
  });
}

/**
 * Convert an HTML element to a PNG data URL using modern-screenshot.
 */
export function toPngModern(element: HTMLElement): Promise<string> {
  return modernScreenshotToPng(element, {
    filter: defaultFilter,
  });
}

export interface ScreenshotComparisonResult {
  htmlToImage: {
    dataUrl: string;
    timeMs: number;
  };
  htmlToImageWithFontEmbed: {
    dataUrl: string;
    timeMs: number;
    fontEmbedTimeMs: number;
  };
  modernScreenshot: {
    dataUrl: string;
    timeMs: number;
  };
  modernScreenshotWorker: {
    dataUrl: string;
    timeMs: number;
    usedWorker: boolean;
  };
}

/**
 * Run both html-to-image and modern-screenshot side-by-side with timing.
 * Includes a test with pre-computed font CSS for html-to-image.
 * Useful for comparing performance and output quality of both libraries.
 */
export async function toPngComparison(
  element: HTMLElement,
  options?: HtmlToImageOptions,
): Promise<ScreenshotComparisonResult> {
  // Run html-to-image with timing (basic)
  const htmlToImageStart = performance.now();
  const htmlToImageResult = await htmlToImageToPng(element, {
    ...defaultHtmlToImageOptions,
    ...options,
  });
  const htmlToImageEnd = performance.now();
  const htmlToImageTime = htmlToImageEnd - htmlToImageStart;

  // Run html-to-image with getFontEmbedCSS (pre-computed font CSS)
  const fontEmbedStart = performance.now();
  const fontEmbedCSS = await getFontEmbedCSS(element, options);
  const fontEmbedEnd = performance.now();
  const fontEmbedTime = fontEmbedEnd - fontEmbedStart;

  const htmlToImageWithFontStart = performance.now();
  const htmlToImageWithFontResult = await htmlToImageToPng(element, {
    ...defaultHtmlToImageOptions,
    ...options,
    fontEmbedCSS, // Use pre-computed font CSS
  });
  const htmlToImageWithFontEnd = performance.now();
  const htmlToImageWithFontTime =
    htmlToImageWithFontEnd - htmlToImageWithFontStart;

  // Run modern-screenshot with timing (no worker)
  const modernStart = performance.now();
  const modernResult = await modernScreenshotToPng(element, {
    filter: defaultFilter,
  });
  const modernEnd = performance.now();
  const modernTime = modernEnd - modernStart;

  // Run modern-screenshot with web worker (with fallback)
  let modernWorkerResult: string;
  let usedWorker = false;

  const modernWorkerStart = performance.now();
  try {
    const context = await createContext(element, {
      workerUrl: workerUrl as string,
      workerNumber: 1,
      filter: defaultFilter,
    });
    try {
      // When using a context, pass it directly without additional options
      modernWorkerResult = await modernScreenshotToPng(context);
      usedWorker = true;
    } finally {
      destroyContext(context);
    }
  } catch (error) {
    // Fallback to non-worker approach if worker fails
    Logger.warn(
      "Worker-based screenshot failed, falling back to main thread:",
      error,
    );
    modernWorkerResult = await modernScreenshotToPng(element, {
      filter: defaultFilter,
    });
  }
  const modernWorkerEnd = performance.now();
  const modernWorkerTime = modernWorkerEnd - modernWorkerStart;

  // Log comparison results
  Logger.warn(
    "Screenshot comparison:\n" +
      `  html-to-image (basic): ${htmlToImageTime.toFixed(2)}ms\n` +
      `  html-to-image (with fontEmbedCSS): ${htmlToImageWithFontTime.toFixed(2)}ms (font embed: ${fontEmbedTime.toFixed(2)}ms, total: ${(fontEmbedTime + htmlToImageWithFontTime).toFixed(2)}ms)\n` +
      `  modern-screenshot: ${modernTime.toFixed(2)}ms\n` +
      `  modern-screenshot (worker): ${modernWorkerTime.toFixed(2)}ms ${usedWorker ? "(used worker)" : "(fallback to main thread)"}\n` +
      `  Winner: ${Math.min(modernTime, modernWorkerTime) < htmlToImageTime ? "modern-screenshot" : "html-to-image"} (vs basic)`,
  );

  return {
    htmlToImage: {
      dataUrl: htmlToImageResult,
      timeMs: htmlToImageTime,
    },
    htmlToImageWithFontEmbed: {
      dataUrl: htmlToImageWithFontResult,
      timeMs: htmlToImageWithFontTime,
      fontEmbedTimeMs: fontEmbedTime,
    },
    modernScreenshot: {
      dataUrl: modernResult,
      timeMs: modernTime,
    },
    modernScreenshotWorker: {
      dataUrl: modernWorkerResult,
      timeMs: modernWorkerTime,
      usedWorker,
    },
  };
}
