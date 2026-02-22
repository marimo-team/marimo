/* Copyright 2026 Marimo. All rights reserved. */
export const Filenames = {
  toMarkdown: (filename: string): string => {
    return Filenames.replace(filename, "md");
  },
  toHTML: (filename: string): string => {
    return Filenames.replace(filename, "html");
  },
  toPNG: (filename: string): string => {
    return Filenames.replace(filename, "png");
  },
  toPDF: (filename: string): string => {
    return Filenames.replace(filename, "pdf");
  },
  toPY: (filename: string): string => {
    return Filenames.replace(filename, "py");
  },
  withoutExtension: (filename: string): string => {
    // Just remove the last extension
    const parts = filename.split(".");
    if (parts.length === 1) {
      return filename;
    }
    return parts.slice(0, -1).join(".");
  },
  replace: (filename: string, extension: string): string => {
    if (filename.endsWith(`.${extension}`)) {
      return filename;
    }
    return `${Filenames.withoutExtension(filename)}.${extension}`;
  },
};

const IMAGE_EXTENSIONS: Record<string, string> = {
  png: "png",
  jpg: "jpg",
  jpeg: "jpeg",
  gif: "gif",
  webp: "webp",
  avif: "avif",
  bmp: "bmp",
  tiff: "tiff",
  svg: "svg",
  "svg+xml": "svg",
};

/**
 * Infers the file extension from an image source string (src).
 * If the extension cannot be determined, it returns `undefined`.
 *
 * @param src - The image source string (a URL or a data URI).
 * @returns The inferred file extension (e.g., "png", "jpeg", "svg"),
 *          or `undefined` if it cannot be determined.
 *
 * @example
 * getImageExtension("https://example.com/image.png");  // Returns "png"
 * getImageExtension("../assets/image.gif");            // Returns "gif"
 * getImageExtension("data:image/svg+xml;base64,...");  // Returns "svg"
 * getImageExtension("https://example.com/image");      // Returns undefined
 */
export function getImageExtension(src: string): string | undefined {
  const dataUriMatch = src.match(/^data:image\/([^,;]+)/);
  if (dataUriMatch) {
    return IMAGE_EXTENSIONS[dataUriMatch[1]];
  }

  try {
    const url = new URL(src, window.location.href);
    const ext = url.pathname.split(".").pop()?.toLowerCase() ?? "";
    return IMAGE_EXTENSIONS[ext];
  } catch {
    return undefined;
  }
}
