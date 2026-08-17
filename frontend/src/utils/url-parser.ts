/* Copyright 2026 Marimo. All rights reserved. */

// Exclude whitespace and the characters that cannot appear unencoded in a URL
// (RFC 3986 excluded/"unwise" set), so linkification stops at delimiters such
// as the closing `"}]` around a URL embedded in JSON text (#10567) instead of
// greedily swallowing them into the href.
const urlRegex = /(https?:\/\/[^\s"'<>`{}|\\^]+)/;
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

  const parts = text.split(urlRegex).filter((part) => part !== "");
  return parts.map((part) => {
    const isUrl = urlRegex.test(part);
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
