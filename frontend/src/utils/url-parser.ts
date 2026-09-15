/* Copyright 2026 Marimo. All rights reserved. */

/** Matches HTTP(S) URLs without consuming surrounding delimiters. */
export const URL_REGEX = /(https?:\/\/[^\s"<>`{}|\\^]+)/;
const imageRegex = /\.(png|jpe?g|gif|webp|svg|ico)(\?.*)?$/i;
const dataImageRegex = /^data:image\//i;
const knownImageDomains = ["avatars.githubusercontent.com"];

export type ContentPart =
  | { type: "text"; value: string }
  | { type: "url"; url: string }
  | { type: "image"; url: string };

/**
 * Parse text content to detect URLs and images
 * Returns an array of content parts that can be text, URL, or image
 */
export function parseContent(text: string): ContentPart[] {
  if (dataImageRegex.test(text)) {
    return [{ type: "image", url: text }];
  }

  const parts = text.split(URL_REGEX).filter((part) => part !== "");
  return parts.map((part) => {
    const isUrl = URL_REGEX.test(part);
    if (isUrl) {
      const isImage =
        imageRegex.test(part) ||
        dataImageRegex.test(part) ||
        knownImageDomains.some((domain) => part.includes(domain));

      if (isImage) {
        return { type: "image", url: part };
      }
      return { type: "url", url: part };
    }
    return { type: "text", value: part };
  });
}
