/* Copyright 2026 Marimo. All rights reserved. */
import type { Base64String } from "@/utils/json/base64";
import type { TypedString } from "@/utils/typed";

// oxlint-disable-next-line typescript/no-explicit-any
export type EventHandler = (...args: any[]) => void;

/**
 * Type-safe widget model id.
 */
export type WidgetModelId = TypedString<"WidgetModelId">;

export function isWidgetModelId(value: unknown): value is WidgetModelId {
  return typeof value === "string" && value.length > 0;
}

/**
 * AnyWidget model state with buffers.
 */
// oxlint-disable-next-line typescript/no-explicit-any
export type ModelState = Record<string | number, any>;

/**
 * Wire format for anywidget state with binary data.
 * Buffers can be either base64 strings (from network) or DataViews (in-memory).
 */
export interface WireFormat<T = Record<string, unknown>> {
  state: T;
  bufferPaths: (string | number)[][];
  buffers: Base64String[];
}

/**
 * Where a widget's ESM can be imported from, and which version.
 * Structural mirror of the backend `EsmSpec`; `hash` keys the module
 * cache and detects code changes (hot reload).
 */
export interface EsmSpec {
  url: string;
  hash: string;
}
