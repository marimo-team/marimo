/* Copyright 2024 Marimo. All rights reserved. */

import type { StaticVirtualFiles } from "./types";
import { deserializeBlob } from "@/utils/blob";
import { getStaticVirtualFiles } from "./static-state";
import type { DataURLString } from "@/utils/json/base64";

/**
 * Patch fetch to resolve virtual files
 */
export function patchFetch(
  files: StaticVirtualFiles = getStaticVirtualFiles(),
) {
  // Store the original fetch function
  const originalFetch = window.fetch;

  // Override the global fetch so when /@file/ is used, it returns the blob data
  window.fetch = async (input, init) => {
    // eslint-disable-next-line @typescript-eslint/no-base-to-string
    const urlString = input instanceof Request ? input.url : input.toString();

    const url =
      urlString.startsWith("/") || urlString.startsWith("./")
        ? new URL(urlString, window.location.origin)
        : new URL(urlString);

    if (files[url.pathname]) {
      const base64 = files[url.pathname];
      const blob = await deserializeBlob(base64);
      return new Response(blob);
    }

    // Fallback to the original fetch
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (originalFetch as any)(input, init);
  };

  return () => {
    window.fetch = originalFetch;
  };
}

export function patchVegaLoader(
  loader: {
    http: (url: string) => Promise<string>;
  },
  files: StaticVirtualFiles = getStaticVirtualFiles(),
) {
  const originalHttp = loader.http.bind(loader);

  loader.http = async (url: string) => {
    const pathname = new URL(url, document.baseURI).pathname;
    if (files[url] || files[pathname]) {
      const base64 = files[url] || files[pathname];
      const blob = await deserializeBlob(base64);
      return blob.text();
    }

    try {
      return await originalHttp(url);
    } catch (error) {
      // If its a data URL, just return the data
      if (url.startsWith("data:")) {
        return deserializeBlob(url as DataURLString).then((blob) =>
          blob.text(),
        );
      }
      // Re-throw the error
      throw error;
    }
  };

  return () => {
    loader.http = originalHttp;
  };
}
