/* Copyright 2026 Marimo. All rights reserved. */

import { prettyError } from "./errors";
import { Logger } from "./Logger";

/**
 * Try to capture iframe content as a data URL.
 * Returns null if the iframe is cross-origin or capture fails.
 */
async function captureIframeContent(
  iframe: HTMLIFrameElement,
  toPng: (element: HTMLElement) => Promise<string>,
): Promise<string | null> {
  try {
    const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!iframeDoc?.body) {
      return null;
    }

    // Replace any nested iframes within this iframe's body before capture.
    // This handles cases like mo.iframe() containing a cross-origin embed.
    const nestedIframes = iframeDoc.body.querySelectorAll("iframe");
    const nestedReplacements: {
      iframe: HTMLIFrameElement;
      placeholder: HTMLElement;
    }[] = [];

    for (const nestedIframe of nestedIframes) {
      if (!nestedIframe.parentNode) {
        continue;
      }
      const placeholder = createIframePlaceholder(nestedIframe);
      nestedReplacements.push({ iframe: nestedIframe, placeholder });
      nestedIframe.replaceWith(placeholder);
    }

    try {
      return await toPng(iframeDoc.body);
    } finally {
      // Restore nested iframes
      for (const { iframe: nested, placeholder } of nestedReplacements) {
        placeholder.replaceWith(nested);
      }
    }
  } catch (error) {
    Logger.debug(`Failed to capture iframe content: ${prettyError(error)}`);
    return null;
  }
}

function createIframePlaceholder(iframe: HTMLIFrameElement): HTMLDivElement {
  const placeholder = document.createElement("div");
  placeholder.style.width = `${iframe.offsetWidth}px`;
  placeholder.style.height = `${iframe.offsetHeight}px`;
  placeholder.style.backgroundColor = "#f5f5f5";
  placeholder.style.display = "flex";
  placeholder.style.alignItems = "center";
  placeholder.style.justifyContent = "center";
  placeholder.style.border = "1px dashed #ccc";
  placeholder.style.color = "#666";
  placeholder.style.fontSize = "12px";
  placeholder.style.textAlign = "center";
  placeholder.style.padding = "8px";
  placeholder.style.boxSizing = "border-box";

  // Extract a readable name from the iframe src
  let label = "Embedded content";
  if (iframe.src) {
    try {
      const url = new URL(iframe.src);
      label = `Embedded: ${url.hostname}`;
    } catch {
      label = "Embedded content";
    }
  }
  placeholder.textContent = `[${label}]`;

  return placeholder;
}

interface IframeReplacement {
  iframe: HTMLIFrameElement;
  replacement: HTMLElement;
}

/**
 * Replace iframes in an element with captured images or placeholders.
 * Returns a cleanup function that restores the original iframes.
 */
export async function replaceIframesForCapture(
  element: HTMLElement,
  toPng: (element: HTMLElement) => Promise<string>,
): Promise<() => void> {
  const iframes = element.querySelectorAll("iframe");
  const replacements: IframeReplacement[] = [];

  for (const iframe of iframes) {
    if (!iframe.parentNode) {
      continue;
    }

    const dataUrl = await captureIframeContent(iframe, toPng);

    let replacement: HTMLElement;
    if (dataUrl) {
      // Create an image with the captured content
      const img = document.createElement("img");
      img.src = dataUrl;
      img.style.width = `${iframe.offsetWidth}px`;
      img.style.height = `${iframe.offsetHeight}px`;
      img.style.display = "block";
      replacement = img;
    } else {
      // Typically cross-origin iframes, we create a placeholder instead
      replacement = createIframePlaceholder(iframe);
    }

    replacements.push({ iframe, replacement });
    iframe.replaceWith(replacement);
  }

  const cleanup = () => {
    for (const { iframe, replacement } of replacements) {
      // Replace the placeholder/image back with the original iframe
      replacement.replaceWith(iframe);
    }
  };
  return cleanup;
}
