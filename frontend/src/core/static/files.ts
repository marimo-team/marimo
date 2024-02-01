/* Copyright 2024 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { VirtualFileTracker } from "./virtual-file-tracker";
import { StaticVirtualFiles } from "./types";
import { deserializeBlob, serializeBlob } from "@/utils/blob";
import { getStaticVirtualFiles } from "./static-state";
import { Sets } from "@/utils/sets";

/**
 * Download virtual files used in the notebook
 */
export async function downloadVirtualFiles(): Promise<StaticVirtualFiles> {
  const files: StaticVirtualFiles = {};

  const virtualFiles = Sets.merge(
    ...VirtualFileTracker.INSTANCE.virtualFiles.values(),
  );

  for (const url of virtualFiles) {
    try {
      const response = await fetch(url);
      const contentType = response.headers.get("Content-Type") ?? "";
      if (!contentType) {
        Logger.warn(`Content-Type header missing for virtual file ${url}`);
      }
      const data = await response.blob();
      const base64 = await serializeBlob(data);
      files[url] = { base64 };
    } catch (error) {
      Logger.warn(`Error downloading virtual file ${url}`, error);
    }
  }

  return files;
}

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

    const url = urlString.startsWith("/")
      ? new URL(urlString, window.location.origin)
      : new URL(urlString);

    if (files[url.pathname]) {
      const { base64 } = files[url.pathname];
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
  const originalHttp = loader.http;

  loader.http = async (url: string) => {
    if (files[url]) {
      const { base64 } = files[url];
      const blob = await deserializeBlob(base64);
      return blob.text();
    }

    return originalHttp(url);
  };

  return () => {
    loader.http = originalHttp;
  };
}
