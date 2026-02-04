import type { Base64String } from "@/utils/json/base64";
import type { TypedString } from "@/utils/typed";

export type EventHandler = (...args: any[]) => void;

/**
 * Type-safe widget model id.
 */
export type WidgetModelId = TypedString<"WidgetModelId">;

/**
 * AnyWidget model state with buffers.
 */
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
