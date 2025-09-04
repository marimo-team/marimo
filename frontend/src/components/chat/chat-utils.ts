/* Copyright 2024 Marimo. All rights reserved. */

import type { FileUIPart } from "ai";
import { blobToString } from "@/utils/fileToBase64";

export async function convertToFileUIPart(
  files: File[],
): Promise<FileUIPart[]> {
  const fileUIParts = await Promise.all(
    files.map(async (file) => {
      const part: FileUIPart = {
        type: "file" as const,
        mediaType: file.type,
        filename: file.name,
        url: await blobToString(file, "dataUrl"),
      };
      return part;
    }),
  );

  return fileUIParts;
}
