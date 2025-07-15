/* Copyright 2024 Marimo. All rights reserved. */
import type { TypedString } from "../typed";

export type JsonString<T = unknown> = TypedString<"Json"> & {
  _of_: T;
};

export type Base64String<T = unknown> = TypedString<"Base64"> & {
  _of_: T;
};

export type ByteString<T = unknown> = TypedString<"ByteString"> & {
  _of_: T;
};

export type DataURLString = `data:${string};base64,${Base64String<string>}`;

// Deserialization: Base64 to String
export function deserializeBase64<T>(base64: Base64String<T>): T {
  const decodedString = decodeURIComponent(atob(base64));
  return decodedString as T;
}

// Deserialization: String to JSON
export function deserializeJson<T>(jsonString: JsonString<T>): T {
  return JSON.parse(jsonString) as T;
}

export function base64ToDataURL<T>(base64: Base64String<T>, mimeType: string) {
  return `data:${mimeType};base64,${base64}`;
}

export function typedAtob<T>(base64: Base64String<T>): ByteString<T> {
  return window.atob(base64) as ByteString<T>;
}

export function typedBtoa<T>(bytes: ByteString<T>): Base64String<T> {
  return window.btoa(bytes) as Base64String<T>;
}

export function isDataURLString(str: string): str is DataURLString {
  return str.startsWith("data:") && str.includes(";base64,");
}

export function extractBase64FromDataURL(str: DataURLString): Base64String {
  return str.split(",")[1] as Base64String;
}

export function byteStringToBinary(bytes: ByteString): Uint8Array {
  return Uint8Array.from(bytes, (c) => c.charCodeAt(0));
}
