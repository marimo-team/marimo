/* Copyright 2026 Marimo. All rights reserved. */
import { Logger } from "./Logger";

/**
 * Copy text to the clipboard. When `html` is provided, writes both
 * text/html and text/plain so rich content (e.g. hyperlinks) is
 * preserved when pasting into apps like Excel or Google Sheets.
 *
 * As of 2024-10-29, Safari does not support navigator.clipboard.writeText
 * when running localhost http.
 */
export async function copyToClipboard(text: string, html?: string) {
  if (navigator.clipboard === undefined) {
    Logger.warn("navigator.clipboard is not supported");
    window.prompt("Copy to clipboard: Ctrl+C, Enter", text);
    return;
  }

  if (html && navigator.clipboard.write) {
    try {
      const item = new ClipboardItem({
        "text/html": new Blob([html], { type: "text/html" }),
        "text/plain": new Blob([text], { type: "text/plain" }),
      });
      await navigator.clipboard.write([item]);
      return;
    } catch {
      Logger.warn("Failed to write rich text, falling back to plain text");
    }
  }

  await navigator.clipboard.writeText(text).catch(() => {
    Logger.warn("Failed to copy to clipboard using navigator.clipboard");
    window.prompt("Copy to clipboard: Ctrl+C, Enter", text);
  });
}

/**
 * Returns true if the current browser is Safari.
 *
 * Safari requires special handling for clipboard operations because it
 * drops the user-activation context during async operations like fetch.
 */
export function isSafari(): boolean {
  const ua = navigator.userAgent;
  // Safari includes "Safari" but not "Chrome"/"Chromium" in its UA string.
  // iOS in-app browsers (CriOS, FxiOS, EdgiOS) also include "Safari"
  // but are excluded by checking for their specific tokens.
  return (
    /safari/i.test(ua) && !/chrome|chromium|crios|fxios|edgios|opios/i.test(ua)
  );
}

/**
 * Copies an image to the clipboard from a URL.
 *
 * On Safari, the ClipboardItem is constructed synchronously with a
 * Promise<Blob> to preserve the user-activation context, which Safari
 * drops during async operations like fetch. This means we must assume
 * the MIME type (image/png) since we can't inspect the response first.
 *
 * On other browsers, we await the fetch and use the actual MIME type.
 */
export async function copyImageToClipboard(imageSrc: string): Promise<void> {
  let item: ClipboardItem;
  if (isSafari()) {
    // Safari drops user-activation context during await, so we must
    // construct the ClipboardItem synchronously with a Promise<Blob>.
    item = new ClipboardItem({
      "image/png": fetch(imageSrc).then((response) => response.blob()),
    });
  } else {
    const response = await fetch(imageSrc);
    const blob = await response.blob();
    item = new ClipboardItem({ [blob.type]: blob });
  }

  await navigator.clipboard.write([item]);
}
