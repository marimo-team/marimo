/* Copyright 2024 Marimo. All rights reserved. */

import type { StaticVirtualFiles } from "./types";
import { getStaticVirtualFiles } from "./static-state";
import { Logger } from "@/utils/Logger";
import type { Loader } from "@/plugins/impl/vega/vega-loader";

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

    if (urlString.startsWith("data:")) {
      return originalFetch(input, init);
    }

    try {
      const url =
        urlString.startsWith("/") || urlString.startsWith("./")
          ? new URL(urlString, window.location.origin)
          : new URL(urlString);

      const filePath = url.pathname;
      if (files[filePath]) {
        const base64 = files[filePath];
        // Convert data URL to blob
        const response = await originalFetch(base64);
        const blob = await response.blob();
        return new Response(blob, {
          headers: {
            "Content-Type": getContentType(filePath),
          },
        });
      }

      // Fallback to the original fetch
      return originalFetch(input, init);
    } catch (error) {
      Logger.error("Error parsing URL", error);
      // If the URL is invalid, just fallback to the original fetch
      return originalFetch(input, init);
    }
  };

  return () => {
    window.fetch = originalFetch;
  };
}

function getContentType(fileName: string): string {
  if (fileName.endsWith(".csv")) {
    return "text/csv";
  }
  if (fileName.endsWith(".json")) {
    return "application/json";
  }
  if (fileName.endsWith(".txt")) {
    return "text/plain";
  }
  // Default to octet-stream if unknown
  return "application/octet-stream";
}

export function patchVegaLoader(
  loader: Loader,
  files: StaticVirtualFiles = getStaticVirtualFiles(),
) {
  const originalHttp = loader.http.bind(loader);
  const originalLoad = loader.load.bind(loader);

  function maybeGetVirtualFile(url: string): string | undefined {
    const pathname = new URL(url, document.baseURI).pathname;
    // Few variations to grab the URL.
    // This can happen if a static file was open at file:// or https://
    return (
      files[url] ||
      files[withoutLeadingDot(url)] ||
      files[pathname] ||
      files[withoutLeadingDot(pathname)]
    );
  }

  loader.http = async (url: string) => {
    const vfile = maybeGetVirtualFile(url);
    if (vfile) {
      // If the file is a virtual file, fetch it
      return await window.fetch(vfile).then((r) => r.text());
    }

    try {
      return await originalHttp(url);
    } catch (error) {
      // If its a data URL, just return the data
      if (url.startsWith("data:")) {
        return await window.fetch(url).then((r) => r.text());
      }
      // Re-throw the error
      throw error;
    }
  };

  loader.load = async (url: string) => {
    const vfile = maybeGetVirtualFile(url);
    if (vfile) {
      // If the file is a virtual file, fetch it
      return await window.fetch(vfile).then((r) => r.text());
    }

    try {
      return await originalLoad(url);
    } catch (error) {
      // If it's a data URL, just return the data
      if (url.startsWith("data:")) {
        return await window.fetch(url).then((r) => r.text());
      }
      // Re-throw the error
      throw error;
    }
  };

  return () => {
    loader.http = originalHttp;
    loader.load = originalLoad;
  };
}

function withoutLeadingDot(path: string): string {
  return path.startsWith(".") ? path.slice(1) : path;
}
