/* Copyright 2026 Marimo. All rights reserved. */

import { AiModelId } from "./ids/ids";
import { getKnownModelMaps } from "./model-registry";

const IMAGE_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
// oxlint-disable-next-line no-control-regex -- Binary detection deliberately matches control characters.
const BINARY_CONTROL_CHARACTERS = /[\x00-\x08\x0B\x0E-\x1F]/;
const TEXT_TYPES = [
  "text/*",
  "application/json",
  "application/xml",
  "application/toml",
  "application/yaml",
  "application/x-yaml",
];

export function getAttachmentMediaType(mediaType: string): string {
  const normalized = mediaType.split(";", 1)[0].trim().toLowerCase();
  if (/^(image|audio|video)\//.test(normalized)) {
    return normalized;
  }
  if (
    isSupportedAttachmentType(normalized, TEXT_TYPES) ||
    normalized.endsWith("+json") ||
    normalized.endsWith("+xml")
  ) {
    return "text/plain";
  }
  return normalized;
}

export async function normalizeAttachment(file: File): Promise<File> {
  let mediaType = getAttachmentMediaType(file.type);
  if (
    mediaType !== "text/plain" &&
    !/^(image|audio|video)\//.test(mediaType) &&
    mediaType !== "application/pdf"
  ) {
    const bytes = new Uint8Array(await file.arrayBuffer());
    try {
      const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      if (!BINARY_CONTROL_CHARACTERS.test(text)) {
        mediaType = "text/plain";
      }
    } catch {
      // Invalid UTF-8 stays binary instead of being decoded with replacement characters.
    }
  }
  return mediaType === file.type
    ? file
    : new File([file], file.name, {
        type: mediaType,
        lastModified: file.lastModified,
      });
}

export function getSupportedAttachmentTypes(model: string): readonly string[] {
  const inputTypes = getKnownModelMaps().modelMap.get(
    AiModelId.parse(model).id,
  )?.input_types;
  // Missing metadata must not prevent custom endpoints from accepting files.
  const isUnknown = !inputTypes?.length;
  return [
    "text/*",
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
