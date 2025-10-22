/* Copyright 2024 Marimo. All rights reserved. */
import DOMPurify, { type Config } from "dompurify";
import { atom, useAtomValue } from "jotai";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { getInitialAppMode } from "@/core/mode";

/**
 * Whether to sanitize the html.
 * When running as an app or with auto_instantiate enabled
 * we ignore sanitization because they should be treated as a website.
 */
const sanitizeHtmlAtom = atom<boolean>((get) => {
  const hasRunAnyCell = get(hasRunAnyCellAtom);

  // If a user has specifically run at least one cell, we don't need to sanitize.
  // HTML needs to be rich to allow for interactive widgets and other dynamic content.
  if (hasRunAnyCell) {
    return false;
  }

  const isInAppMode = getInitialAppMode() === "read";
  // Apps need to run javascript and load external resources.
  if (isInAppMode) {
    return false;
  }

  return true;
});

/**
 * Whether to sanitize the html.
 */
export function useSanitizeHtml() {
  return useAtomValue(sanitizeHtmlAtom);
}

// preserve target=_blank https://github.com/cure53/DOMPurify/issues/317#issuecomment-912474068
const TEMPORARY_ATTRIBUTE = "data-temp-href-target";
DOMPurify.addHook("beforeSanitizeAttributes", (node) => {
  if (node.tagName === "A") {
    if (!node.hasAttribute("target")) {
      node.setAttribute("target", "_self");
    }

    if (node.hasAttribute("target")) {
      node.setAttribute(TEMPORARY_ATTRIBUTE, node.getAttribute("target") || "");
    }
  }
});

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.tagName === "A" && node.hasAttribute(TEMPORARY_ATTRIBUTE)) {
    node.setAttribute("target", node.getAttribute(TEMPORARY_ATTRIBUTE) || "");
    node.removeAttribute(TEMPORARY_ATTRIBUTE);
    if (node.getAttribute("target") === "_blank") {
      node.setAttribute("rel", "noopener");
    }
  }
});

/**
 * This removes script tags, form tags, iframe tags, and other potentially dangerous tags
 */
export function sanitizeHtml(html: string) {
  const sanitizationOptions: Config = {
    // Default to permit HTML, SVG and MathML, this limits to HTML only
    USE_PROFILES: { html: true, svg: true, mathMl: true },
    // glue elements like style, script or others to document.body and prevent unintuitive browser behavior in several edge-cases
    FORCE_BODY: true,
    CUSTOM_ELEMENT_HANDLING: {
      tagNameCheck: /^marimo-[A-Za-z][\w-]*$/,
      attributeNameCheck: /^[A-Za-z][\w-]*$/,
    },
  };
  return DOMPurify.sanitize(html, sanitizationOptions);
}
