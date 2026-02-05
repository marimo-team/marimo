/* Copyright 2026 Marimo. All rights reserved. */

const PLACEHOLDER_WIDTH = 320;
const PLACEHOLDER_HEIGHT = 180;

function isExternalUrl(src: string | null): string | null {
  if (!src || src === "about:blank") {
    return null;
  }
  try {
    const resolved = new URL(src, window.location.href);
    if (resolved.origin === window.location.origin) {
      return null;
    }
    return resolved.href;
  } catch {
    return src;
  }
}

function wrapText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string[] {
  const lines: string[] = [];
  let current = "";

  for (const char of text) {
    const test = current + char;
    if (ctx.measureText(test).width <= maxWidth) {
      current = test;
    } else {
      if (current) {
        lines.push(current);
      }
      current = char;
    }
  }
  if (current) {
    lines.push(current);
  }

  return lines;
}

function createPlaceholderImage(url: string | null): string {
  const scale = window.devicePixelRatio || 1;
  const canvas = document.createElement("canvas");
  canvas.width = PLACEHOLDER_WIDTH * scale;
  canvas.height = PLACEHOLDER_HEIGHT * scale;

  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return canvas.toDataURL("image/png");
  }

  ctx.scale(scale, scale);

  // Background
  ctx.fillStyle = "#f3f4f6";
  ctx.fillRect(0, 0, PLACEHOLDER_WIDTH, PLACEHOLDER_HEIGHT);

  // Border
  ctx.strokeStyle = "#d1d5db";
  ctx.strokeRect(0.5, 0.5, PLACEHOLDER_WIDTH - 1, PLACEHOLDER_HEIGHT - 1);

  // Text
  ctx.fillStyle = "#6b7280";
  ctx.font = "8px sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const lineHeight = 14;
  const padding = 16;
  const maxWidth = PLACEHOLDER_WIDTH - padding * 2;

  const message = "External iframe";
  const urlLines = url ? wrapText(ctx, url, maxWidth) : [];
  const totalLines = 1 + urlLines.length;
  const totalHeight = totalLines * lineHeight;
  let y = (PLACEHOLDER_HEIGHT - totalHeight) / 2 + lineHeight / 2;

  ctx.fillText(message, PLACEHOLDER_WIDTH / 2, y);
  y += lineHeight;

  for (const line of urlLines) {
    ctx.fillText(line, PLACEHOLDER_WIDTH / 2, y);
    y += lineHeight;
  }

  return canvas.toDataURL("image/png");
}

/**
 * Capture external iframes as a PNG image. External iframes are not supported by html-to-image.
 * @param element - The element to capture the iframe from
 * @returns The image data URL of the iframe, or a placeholder image if the iframe is external
 */
export async function captureExternalIframes(
  element: HTMLElement,
): Promise<string | null> {
  const iframe = element.querySelector("iframe");
  if (!iframe) {
    return null;
  }

  // Check if the iframe itself is external
  const externalUrl = isExternalUrl(iframe.getAttribute("src"));
  if (externalUrl) {
    return createPlaceholderImage(externalUrl);
  }

  // Try to access iframe document and check for nested external iframes
  let doc: Document;
  try {
    const d = iframe.contentDocument || iframe.contentWindow?.document;
    if (!d?.body) {
      return null;
    }
    doc = d;
  } catch {
    return createPlaceholderImage(null);
  }

  // Check for nested external iframes
  for (const nested of doc.querySelectorAll("iframe")) {
    const nestedExternal = isExternalUrl(nested.getAttribute("src"));
    if (nestedExternal) {
      return createPlaceholderImage(nestedExternal);
    }
  }

  return null;
}
