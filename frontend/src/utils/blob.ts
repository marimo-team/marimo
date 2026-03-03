/* Copyright 2026 Marimo. All rights reserved. */
import type { DataURLString } from "./json/base64";

export function serializeBlob<T>(blob: Blob): Promise<DataURLString> {
  return new Promise<DataURLString>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      resolve(event.target?.result as DataURLString);
    };
    reader.onerror = (evt) => {
      reject(new Error(`Failed to read blob: ${evt.type}`));
    };
    reader.readAsDataURL(blob);
  });
}

export function deserializeBlob(serializedBlob: DataURLString): Blob {
  // Extract the base64 data from the data URL
  const [prefix, base64Data] = serializedBlob.split(",", 2);
  const mimeType = /^data:(.+);base64$/.exec(prefix)?.[1];
  // Decode the base64 string
  const binaryString = atob(base64Data);
  // Convert the binary string to an array buffer
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  // Create a new Blob from the array buffer
  const blob = new Blob([bytes], { type: mimeType });
  return blob;
}
