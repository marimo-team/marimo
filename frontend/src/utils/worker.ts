/* Copyright 2026 Marimo. All rights reserved. */

/** Load a module worker across origins, including from file:// pages. */
export function createModuleWorker(url: URL, options: WorkerOptions): Worker {
  if (url.origin === globalThis.origin) {
    return new Worker(url.href, { ...options, type: "module" });
  }
  const js = `import ${JSON.stringify(url.href)}`;
  // Blob workers preserve the page origin, but file:// needs a data URL.
  const source =
    globalThis.origin === "null"
      ? `data:application/javascript,${encodeURIComponent(js)}`
      : URL.createObjectURL(new Blob([js], { type: "application/javascript" }));
  try {
    return new Worker(source, { ...options, type: "module" });
  } finally {
    if (source.startsWith("blob:")) {
      // Worker() captures the Blob before returning, even while imports load.
      URL.revokeObjectURL(source);
    }
  }
}
