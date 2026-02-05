/* Copyright 2026 Marimo. All rights reserved. */
// @ts-expect-error - no types
import * as vl from "vega-loader";
import type { DataFormat } from "./types";
import type { DataType } from "./vega-loader";

// Re-export the vega-loader functions to add TypeScript types

export function read<T = object>(
  data: string | Record<string, unknown> | Record<string, unknown>[],
  format:
    | DataFormat
    | {
        type: DataFormat["type"];
        parse: "auto";
      }
    | {
        type: DataFormat["type"];
        parse: Record<string, DataType>;
      }
    | undefined,
): T[] {
  return vl.read(data, format);
}

export interface Loader {
  load(
    uri: string,
    options?: unknown,
  ): Promise<string | Record<string, unknown> | Record<string, unknown>[]>;
  sanitize(uri: string, options?: unknown): Promise<{ href: string }>;
  http(uri: string, options?: unknown): Promise<string>;
  file(filename: string): Promise<string>;
}

export function createLoader(): Loader {
  return vl.loader();
}

export type VegaDataType =
  | "boolean"
  | "integer"
  | "number"
  | "date"
  | "string"
  | "unknown";

export type FieldTypes = Record<string, VegaDataType>;

export const typeParsers: Record<VegaDataType, (value: string) => unknown> =
  vl.typeParsers;

export type { DataType } from "@/core/kernel/messages";
