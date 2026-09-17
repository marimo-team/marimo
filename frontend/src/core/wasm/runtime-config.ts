/* Copyright 2026 Marimo. All rights reserved. */

export interface WasmRuntimeConfig {
  pyodideIndexUrl?: string;
  pyodideLockfileUrl?: string;
  pypiIndexUrl?: string;
}

export function getWasmRuntimeConfig(): WasmRuntimeConfig {
  const element = document.querySelector<HTMLElement>("marimo-wasm");
  const resolve = (url: string | undefined) => {
    try {
      return url ? new URL(url, document.baseURI).href : undefined;
    } catch {
      return undefined;
    }
  };
  return {
    pyodideIndexUrl: resolve(element?.dataset.pyodideIndexUrl),
    pyodideLockfileUrl: resolve(element?.dataset.pyodideLockfileUrl),
    // URL serialization escapes the placeholder understood by micropip.
    pypiIndexUrl: resolve(element?.dataset.pypiIndexUrl)?.replaceAll(
      "%7Bpackage_name%7D",
      "{package_name}",
    ),
  };
}
