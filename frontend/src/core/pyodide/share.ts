/* Copyright 2024 Marimo. All rights reserved. */
import { compressToEncodedURIComponent } from "lz-string";

export function createShareableLink(code: string) {
  const compressed = compressToEncodedURIComponent(code);
  const url = new URL("https://marimo.app");
  url.searchParams.set("code", compressed);
  return url.href;
}
