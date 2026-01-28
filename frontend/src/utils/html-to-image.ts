/* Copyright 2026 Marimo. All rights reserved. */
import { toPng as htmlToImageToPng } from "html-to-image";
import { Logger } from "./Logger";

export type HtmlToImageOptions = Parameters<typeof htmlToImageToPng>[1];

// For improved performance, we include these styles that are likely to be present on the element.
export const necessaryStyleProperties = [
  // Sizing
  "width",
  "height",
  "min-width",
  "min-height",
  "max-width",
  "max-height",
  "box-sizing",
  "aspect-ratio",

  // Display & Layout
  "display",
  "position",
  "top",
  "left",
  "bottom",
  "right",
  "z-index",
  "float",
  "clear",

  // Flexbox
  "flex",
  "flex-direction",
  "flex-wrap",
  "flex-grow",
  "flex-shrink",
  "flex-basis",
  "align-items",
  "align-self",
  "justify-content",
  "gap",
  "order",

  // Grid
  "grid-template-columns",
  "grid-template-rows",
  "grid-column",
  "grid-row",
  "row-gap",
  "column-gap",

  // Spacing
  "margin",
  "margin-top",
  "margin-right",
  "margin-bottom",
  "margin-left",
  "padding",
  "padding-top",
  "padding-right",
  "padding-bottom",
  "padding-left",

  // Typography
  "font",
  "font-family",
  "font-size",
  "font-weight",
  "font-style",
  "line-height",
  "letter-spacing",
  "word-spacing",
  "text-align",
  "text-decoration",
  "text-transform",
  "text-indent",
  "text-shadow",
  "white-space",
  "text-wrap",
  "word-break",
  "text-overflow",
  "vertical-align",
  "color",

  // Background
  "background",
  "background-color",
  "background-image",
  "background-size",
  "background-position",
  "background-repeat",
  "background-clip",

  // Borders
  "border",
  "border-width",
  "border-style",
  "border-color",
  "border-top",
  "border-right",
  "border-bottom",
  "border-left",
  "border-radius",
  "outline",

  // Effects
  "box-shadow",
  "text-shadow",
  "opacity",
  "filter",
  "backdrop-filter",
  "mix-blend-mode",
  "transform",
  "clip-path",

  // Overflow & Visibility
  "overflow",
  "overflow-x",
  "overflow-y",
  "visibility",

  // SVG
  "fill",
  "stroke",
  "stroke-width",

  // Images & Objects
  "object-fit",
  "object-position",

  // Lists
  "list-style",
  "list-style-type",

  // Tables
  "border-collapse",
  "border-spacing",

  // Misc
  "content",
  "cursor",
];

/**
 * Default options for html-to-image conversions.
 * These handle common edge cases like filtering out toolbars and logging errors.
 */
export const defaultHtmlToImageOptions: HtmlToImageOptions = {
  filter: (node) => {
    try {
      if ("classList" in node) {
        const classes = node.classList;
        if (
          classes.contains("mpl-toolbar") ||
          classes.contains("print:hidden")
        ) {
          return false;
        }
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
  includeStyleProperties: necessaryStyleProperties,
};

/**
 * Convert an HTML element to a PNG data URL.
 * This is a wrapper around html-to-image's toPng with default options applied.
 */
export async function toPng(
  element: HTMLElement,
  options?: HtmlToImageOptions,
): Promise<string> {
  return htmlToImageToPng(element, {
    ...defaultHtmlToImageOptions,
    ...options,
  });
}
