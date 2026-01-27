/* Copyright 2026 Marimo. All rights reserved. */
import { toPng as htmlToImageToPng } from "html-to-image";
import { Logger } from "./Logger";

export type HtmlToImageOptions = Parameters<typeof htmlToImageToPng>[1];

/**
 * Default options for html-to-image conversions.
 * These handle common edge cases like filtering out toolbars and logging errors.
 */
export const defaultHtmlToImageOptions: HtmlToImageOptions = {
  filter: (node) => {
    try {
      if ("classList" in node) {
        // Filter out matplotlib toolbars
        return !node.classList.contains("mpl-toolbar");
      }
      return true;
    } catch (error) {
      Logger.error("Error filtering node:", error);
      return true;
    }
  },
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
  return htmlToImageToPng(element, {
    ...defaultHtmlToImageOptions,
    ...options,
  });
}
