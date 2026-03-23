/* Copyright 2026 Marimo. All rights reserved. */
import DOMPurify, { type Config } from "dompurify";

// preserve target=_blank https://github.com/cure53/DOMPurify/issues/317#issuecomment-912474068
// Guard for non-browser environments (e.g. Node.js in the marimo-lsp extension)
// where `document` is not available.
if (typeof document !== "undefined") {
  const TEMPORARY_ATTRIBUTE = "data-temp-href-target";
  DOMPurify.addHook("beforeSanitizeAttributes", (node) => {
    if (node.tagName === "A") {
      if (!node.hasAttribute("target")) {
        node.setAttribute("target", "_self");
      }

      if (node.hasAttribute("target")) {
        node.setAttribute(
          TEMPORARY_ATTRIBUTE,
          node.getAttribute("target") || "",
        );
      }
    }
  });

  DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A" && node.hasAttribute(TEMPORARY_ATTRIBUTE)) {
      node.setAttribute("target", node.getAttribute(TEMPORARY_ATTRIBUTE) || "");
      node.removeAttribute(TEMPORARY_ATTRIBUTE);
      if (node.getAttribute("target") === "_blank") {
        node.setAttribute("rel", "noopener noreferrer");
      }
    }
  });
}

/**
 * This removes script tags, form tags, iframe tags, and other potentially dangerous tags
 */
export function sanitizeHtml(html: string) {
  const sanitizationOptions: Config = {
    // Default to permit HTML, SVG and MathML, this limits to HTML only
    USE_PROFILES: { html: true, svg: true, mathMl: true },
    // Allow SVG <use> elements and their href attributes, which are needed
    // for SVGs that reference <defs> (e.g., Matplotlib SVG output).
    ADD_TAGS: ["use"],
    ADD_ATTR: ["href", "xlink:href"],
    // glue elements like style, script or others to document.body and prevent unintuitive browser behavior in several edge-cases
    FORCE_BODY: true,
    CUSTOM_ELEMENT_HANDLING: {
      tagNameCheck: /^(marimo-[A-Za-z][\w-]*|iconify-icon)$/,
      attributeNameCheck: /^[A-Za-z][\w-]*$/,
    },
    // This flag means we should sanitize such that is it safe for XML,
    // but this is only used for HTML content.
    SAFE_FOR_XML: !html.includes("marimo-mermaid"),
  };
  return DOMPurify.sanitize(html, sanitizationOptions);
}
