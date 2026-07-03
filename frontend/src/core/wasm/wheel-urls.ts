/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";

const ALLOWED_WHEEL_URL_PROTOCOLS = new Set(["blob:", "http:", "https:"]);

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
      if (!ALLOWED_WHEEL_URL_PROTOCOLS.has(parsedUrl.protocol)) {
        Logger.warn("Ignoring included WASM wheel with unsupported protocol", {
          protocol: parsedUrl.protocol,
          url,
        });
        return [];
      }

      if (parsedUrl.origin !== allowedOrigin) {
        Logger.warn("Ignoring included WASM wheel from another origin", {
          allowedOrigin,
          origin: parsedUrl.origin,
          url,
        });
        return [];
      }

      if (
        parsedUrl.protocol !== "blob:" &&
        !parsedUrl.pathname.toLowerCase().endsWith(".whl")
      ) {
        Logger.warn("Ignoring included WASM wheel URL without .whl path", {
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
