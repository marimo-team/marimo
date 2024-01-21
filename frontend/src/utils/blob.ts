/* Copyright 2024 Marimo. All rights reserved. */
import { Base64String } from "./json/base64";

export function serializeBlob(blob: Blob): Promise<Base64String> {
  return new Promise<Base64String>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (event) => {
      resolve(event.target?.result as Base64String);
    };
    reader.onerror = (error) => {
      reject(error);
    };
    reader.readAsDataURL(blob);
  });
}

export function deserializeBlob(serializedBlob: Base64String): Promise<Blob> {
  return new Promise((resolve, reject) => {
    try {
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
      resolve(blob);
    } catch (error) {
      reject(error);
    }
  });
}
