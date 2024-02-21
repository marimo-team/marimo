/* Copyright 2024 Marimo. All rights reserved. */
import { compressToEncodedURIComponent } from "lz-string";

export function createShareableLink(opts: {
  code: string | null;
  baseUrl?: string;
  filename?: string | null;
}): string {
  const { code, baseUrl = "https://marimo.app", filename } = opts;
  const url = new URL(baseUrl);
  if (code) {
    const compressed = compressToEncodedURIComponent(code);
    url.searchParams.set("code", compressed);
  }
  if (filename) {
    url.searchParams.set("filename", filename);
  }
  return url.href;
}
