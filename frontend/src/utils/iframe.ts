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

// Default browser intrinsic size for iframes per CSS spec
// https://stackoverflow.com/questions/5871668/default-width-height-of-an-iframe
const MIN_PLACEHOLDER_WIDTH = 300;
const MIN_PLACEHOLDER_HEIGHT = 150;

function createIframePlaceholder(iframe: HTMLIFrameElement): HTMLDivElement {
  const placeholder = document.createElement("div");
  placeholder.style.width = `${iframe.offsetWidth}px`;
  placeholder.style.height = `${iframe.offsetHeight}px`;
  // Fallback minimum dimensions in case iframe is hidden or not yet rendered
  placeholder.style.minWidth = `${MIN_PLACEHOLDER_WIDTH}px`;
  placeholder.style.minHeight = `${MIN_PLACEHOLDER_HEIGHT}px`;
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

function createIframeImage(
  iframe: HTMLIFrameElement,
  dataUrl: string,
): HTMLImageElement {
  const img = document.createElement("img");
  img.src = dataUrl;
  img.style.width = `${iframe.offsetWidth}px`;
  img.style.height = `${iframe.offsetHeight}px`;
  img.style.display = "block";
  return img;
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

    const replacement = dataUrl
      ? createIframeImage(iframe, dataUrl)
      : // Typically cross-origin iframes, we create a placeholder instead
        createIframePlaceholder(iframe);

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

/**
 * Replace iframes in a clone with captured images or placeholders.
 * Uses the source element's iframes for capture without mutating the source.
 */
export async function replaceIframesForCaptureInClone(
  source: HTMLElement,
  clone: HTMLElement,
  toPng: (element: HTMLElement) => Promise<string>,
): Promise<void> {
  const sourceIframes = [...source.querySelectorAll("iframe")];
  const cloneIframes = [...clone.querySelectorAll("iframe")];

  if (sourceIframes.length !== cloneIframes.length) {
    Logger.debug(
      `Iframe count mismatch for clone capture: source=${sourceIframes.length}, clone=${cloneIframes.length}`,
    );
  }

  const count = Math.min(sourceIframes.length, cloneIframes.length);
  for (let i = 0; i < count; i++) {
    const sourceIframe = sourceIframes[i];
    const cloneIframe = cloneIframes[i];
    if (!cloneIframe?.parentNode) {
      continue;
    }

    const dataUrl = await captureIframeContent(sourceIframe, toPng);
    const replacement = dataUrl
      ? createIframeImage(sourceIframe, dataUrl)
      : createIframePlaceholder(sourceIframe);
    cloneIframe.replaceWith(replacement);
  }
}

function createOffscreenClone(element: HTMLElement): {
  clone: HTMLElement;
  cleanup: () => void;
} {
  const container = document.createElement("div");
  const rect = element.getBoundingClientRect();

  container.style.position = "absolute";
  container.style.left = "-10000px";
  container.style.top = "0";
  container.style.width = `${Math.max(1, rect.width)}px`;
  container.style.height = `${Math.max(1, rect.height)}px`;
  container.style.opacity = "0";
  container.style.pointerEvents = "none";
  container.setAttribute("aria-hidden", "true");

  const clone = element.cloneNode(true) as HTMLElement;
  container.append(clone);

  const mountPoint =
    element.parentElement ?? document.getElementById("App") ?? document.body;
  mountPoint.append(container);

  return {
    clone,
    cleanup: () => {
      container.remove();
    },
  };
}

export async function getIframeCaptureTarget(
  element: HTMLElement,
  toPng: (element: HTMLElement) => Promise<string>,
): Promise<{
  target: HTMLElement;
  cleanup: () => void;
  restoreIframes?: () => void;
}> {
  if (!element.querySelector("iframe")) {
    return { target: element, cleanup: () => undefined };
  }

  try {
    const { clone, cleanup } = createOffscreenClone(element);
    await replaceIframesForCaptureInClone(element, clone, toPng);
    return { target: clone, cleanup };
  } catch (error) {
    Logger.debug(`Clone capture failed, falling back: ${prettyError(error)}`);
    const restoreIframes = await replaceIframesForCapture(element, toPng);
    return {
      target: element,
      cleanup: () => undefined,
      restoreIframes,
    };
  }
}
