/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";

export function resolveWasmWheelUrls(
  urls: string[],
  opts: { baseUrl: string; allowedOrigin: string },
): string[] {
  const { allowedOrigin, baseUrl } = opts;

  return urls.flatMap((url) => {
    const trimmedUrl = url.trim();
    if (trimmedUrl.length === 0) {
      Logger.warn("Ignoring empty included WASM wheel URL");
      return [];
    }

    try {
      const parsedUrl = new URL(trimmedUrl, baseUrl);
      if (parsedUrl.origin !== allowedOrigin) {
        Logger.warn("Ignoring included WASM wheel from another origin", {
          allowedOrigin,
          origin: parsedUrl.origin,
          url,
        });
        return [];
      }

      return [parsedUrl.toString()];
    } catch (error) {
      Logger.warn("Ignoring invalid included WASM wheel URL", { error, url });
      return [];
    }
  });
}
