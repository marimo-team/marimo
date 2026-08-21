/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Matches an `http(s)` URL, stopping at whitespace and the characters that
 * cannot appear unencoded in a URL (the RFC 3986 excluded/"unwise" set:
 * `" ' < > \` { } | \ ^`). This keeps linkification from greedily swallowing
 * trailing delimiters such as the closing `"}]` around a URL embedded in JSON
 * text (#10567) into the href, while preserving characters that are valid in
 * real URLs (`. , ( ) [ ]`, query strings, etc.).
 *
 * Shared so the table-cell linkifier here and the JSON-viewer linkifier in
 * `json/json-parser.ts` stay in sync (build a global copy with
 * `new RegExp(URL_REGEX.source, "g")`).
 */
export const URL_REGEX = /(https?:\/\/[^\s"'<>`{}|\\^]+)/;
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
