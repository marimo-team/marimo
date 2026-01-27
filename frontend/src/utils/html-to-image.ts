/* Copyright 2026 Marimo. All rights reserved. */
import {
  createContext,
  destroyContext,
  domToPng,
  type Options as ModernScreenshotOptions,
} from "modern-screenshot";
import workerUrl from "modern-screenshot/worker?url";
import { Logger } from "./Logger";

export type { ModernScreenshotOptions };

/**
 * Filter function that excludes matplotlib toolbars from screenshots.
 */
function defaultFilter(node: Node): boolean {
  try {
    if ("classList" in node) {
      const element = node as Element;
      return !element.classList.contains("mpl-toolbar");
    }
    return true;
  } catch (error) {
    Logger.error("Error filtering node:", error);
    return true;
  }
}

/**
 * Default options for modern-screenshot conversions.
 */
export const defaultScreenshotOptions: ModernScreenshotOptions = {
  filter: defaultFilter,
};

/**
 * Convert an HTML element to a PNG data URL using modern-screenshot.
 * Tries to use a web worker for better performance, falls back to main thread if worker fails.
 */
export async function toPng(
  element: HTMLElement,
  options?: ModernScreenshotOptions,
): Promise<string> {
  const mergedOptions = { ...defaultScreenshotOptions, ...options };

  try {
    // Try worker-based approach first
    const context = await createContext(element, {
      ...mergedOptions,
      workerUrl: workerUrl,
      workerNumber: 1,
    });
    try {
      return await domToPng(context);
    } finally {
      destroyContext(context);
    }
  } catch (error) {
    // Fallback to main thread if worker fails
    Logger.warn(
      "Worker-based screenshot failed, falling back to main thread:",
      error,
    );
    return domToPng(element, mergedOptions);
  }
}
