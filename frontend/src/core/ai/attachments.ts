/* Copyright 2026 Marimo. All rights reserved. */

import { AiModelId } from "./ids/ids";
import { getKnownModelMaps } from "./model-registry";

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
const TEXT_TYPES = [
  "text/*",
  "application/json",
  "application/xml",
  "application/toml",
  "application/yaml",
  "application/x-yaml",
  "application/javascript",
  "application/ecmascript",
  "application/x-javascript",
  "application/sql",
  "application/x-sh",
  "application/jsonl",
  "application/x-ndjson",
];
const TEXT_EXTENSIONS = [
  ".txt",
  ".md",
  ".markdown",
  ".csv",
  ".tsv",
  ".json",
  ".jsonl",
  ".ndjson",
  ".ipynb",
  ".xml",
  ".toml",
  ".yaml",
  ".yml",
  ".py",
  ".sql",
  ".r",
  ".js",
  ".mjs",
  ".cjs",
  ".jsx",
  ".ts",
  ".tsx",
  ".html",
  ".htm",
  ".css",
  ".sh",
];

export function getAttachmentMediaType(
  mediaType: string,
  filename?: string,
): string {
  const normalized = mediaType.split(";", 1)[0].trim().toLowerCase();
  if (
    isSupportedAttachmentType(normalized, TEXT_TYPES) ||
    normalized.endsWith("+json") ||
    normalized.endsWith("+xml")
  ) {
    return "text/plain";
  }
  if (
    (!normalized || normalized === "application/octet-stream") &&
    filename &&
    TEXT_EXTENSIONS.some((extension) =>
      filename.toLowerCase().endsWith(extension),
    )
  ) {
    return "text/plain";
  }
  return normalized;
}

export function getSupportedAttachmentTypes(model: string): readonly string[] {
  const inputTypes = getKnownModelMaps().modelMap.get(
    AiModelId.parse(model).id,
  )?.input_types;
  // Missing metadata must not prevent custom endpoints from accepting files.
  const isUnknown = !inputTypes?.length;
  return [
    ...TEXT_TYPES,
    ...TEXT_EXTENSIONS,
    ...(isUnknown || inputTypes.includes("image") ? IMAGE_TYPES : []),
    ...(isUnknown || inputTypes.includes("pdf") ? ["application/pdf"] : []),
  ];
}

export function isSupportedAttachmentType(
  mediaType: string,
  supportedTypes: readonly string[],
): boolean {
  return supportedTypes.some((supported) =>
    supported.endsWith("/*")
      ? mediaType.startsWith(supported.slice(0, -1))
      : mediaType === supported,
  );
}
