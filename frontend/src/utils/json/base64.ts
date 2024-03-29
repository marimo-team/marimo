/* Copyright 2024 Marimo. All rights reserved. */
import { TypedString } from "../typed";

export type Base64String = TypedString<"Base64">;

// Serialization: JSON to Base64
export function serializeJsonToBase64(jsonObject: object) {
  const jsonString = JSON.stringify(jsonObject);
  return btoa(encodeURIComponent(jsonString)) as Base64String;
}

// Deserialization: Base64 to JSON
export function deserializeBase64ToJson<T>(base64: Base64String): T {
  const decodedString = decodeURIComponent(atob(base64));
  return JSON.parse(decodedString) as T;
}

export function base64ToDataURL(base64: Base64String, mimeType: string) {
  return `data:${mimeType};base64,${base64}`;
}
