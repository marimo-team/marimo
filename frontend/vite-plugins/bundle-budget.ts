/* Copyright 2026 Marimo. All rights reserved. */

import { gzipSync } from "node:zlib";
import type { Plugin, Rolldown } from "vite";

type Chunk = Pick<
  Rolldown.OutputChunk,
  "fileName" | "isEntry" | "imports" | "code"
>;

export function initialBundleSize(chunks: Chunk[]) {
  const byName = new Map(chunks.map((chunk) => [chunk.fileName, chunk]));
  const visited = new Set<string>();
  let bytes = 0;
  let gzipBytes = 0;

  function visit(fileName: string) {
    const chunk = byName.get(fileName);
    if (!chunk || visited.has(fileName)) {
      return;
    }
    visited.add(fileName);
    bytes += Buffer.byteLength(chunk.code);
    gzipBytes += gzipSync(chunk.code).byteLength;
    chunk.imports.forEach(visit);
  }

  chunks
    .filter((chunk) => chunk.isEntry)
    .forEach((chunk) => visit(chunk.fileName));
  return { bytes, gzipBytes };
}

/** Budget the entry points and their static JS imports, excluding lazy chunks. */
export function bundleBudget({
  name,
  maxGzipKiB,
}: {
  name: string;
  maxGzipKiB: number;
}): Plugin {
  return {
    name: "marimo-bundle-budget",
    apply: "build",
    generateBundle: {
      order: "post",
      handler(_options, bundle) {
        const size = initialBundleSize(
          Object.values(bundle).filter((entry) => entry.type === "chunk"),
        );
        if (size.gzipBytes > maxGzipKiB * 1024) {
          this.error(
            `${name} initial JavaScript is ${(size.gzipBytes / 1024).toFixed(1)} KiB gzip ` +
              `(${(size.bytes / 1024).toFixed(1)} KiB raw), exceeding the ${maxGzipKiB} KiB budget. ` +
              "Check for new eager imports before increasing the budget.",
          );
        }
      },
    },
  };
}
