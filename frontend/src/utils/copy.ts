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
