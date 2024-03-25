/* Copyright 2024 Marimo. All rights reserved. */
import { compressToEncodedURIComponent } from "lz-string";

export function createShareableLink(opts: {
  code: string | null;
  baseUrl?: string;
}): string {
  const { code, baseUrl = "https://marimo.app" } = opts;
  const url = new URL(baseUrl);
  if (code) {
    const compressed = compressToEncodedURIComponent(code);
    url.hash = `#code/${compressed}`;
  }
  return url.href;
}
