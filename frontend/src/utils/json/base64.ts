/* Copyright 2026 Marimo. All rights reserved. */

import type { NotificationMessageData } from "@/core/kernel/messages";
import type { TypedString } from "../typed";

/**
 * A JSON string of a given type.
 */
export type JsonString<T = unknown> = TypedString<"Json"> & {
  _of_: T;
};

/**
 * A base64-encoded string.
 */
export type Base64String = TypedString<"Base64">;

/**
 * A data URL string.
 */
export type DataURLString = `data:${string};base64,${Base64String}`;

/**
 * Typed JSON deserialization.
 */
export function deserializeJson<T>(jsonString: JsonString<T>): T {
  return JSON.parse(jsonString) as T;
}

/**
 * Convert a base64 string to a data URL string.
 */
export function base64ToDataURL(
  base64: Base64String,
  mimeType: string,
): DataURLString {
  return `data:${mimeType};base64,${base64}`;
}

/**
 * Check if a string is a data URL string.
 */
export function isDataURLString(str: string): str is DataURLString {
  return str.startsWith("data:") && str.includes(";base64,");
}

/**
 * Extract the base64 string from a data URL string.
 */
export function extractBase64FromDataURL(str: DataURLString): Base64String {
  return str.split(",")[1] as Base64String;
}

/**
 * Convert a base64 string to a Uint8Array.
 */
export function base64ToUint8Array(bytes: Base64String): Uint8Array {
  const binary = window.atob(bytes);
  return Uint8Array.from(binary, (c) => c.charCodeAt(0));
}

/**
 * Convert a base64 string to a DataView.
 */
export function base64ToDataView(bytes: Base64String): DataView {
  const uint8Array = base64ToUint8Array(bytes);
  return new DataView(uint8Array.buffer);
}

/**
 * Convert a Uint8Array to a base64 string.
 */
export function uint8ArrayToBase64(binary: Uint8Array): Base64String {
  const chars = Array.from(binary, (byte) => String.fromCharCode(byte));
  return window.btoa(chars.join("")) as Base64String;
}

/**
 * Convert a DataView to a base64 string.
 */
export function dataViewToBase64(dataView: DataView): Base64String {
  const uint8Array = new Uint8Array(
    dataView.buffer,
    dataView.byteOffset,
    dataView.byteLength,
  );
  return uint8ArrayToBase64(uint8Array);
}

export function safeExtractSetUIElementMessageBuffers(
  notification: NotificationMessageData<"send-ui-element-message">,
): readonly DataView[] {
  // @ts-expect-error - TypeScript doesn't know that these strings are actually base64 strings
  const strs: Base64String[] = notification.buffers ?? [];
  return strs.map(base64ToDataView);
}
