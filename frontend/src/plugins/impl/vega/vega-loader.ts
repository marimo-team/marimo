/* Copyright 2024 Marimo. All rights reserved. */
// @ts-expect-error - no types
import * as vl from "vega-loader";
import { DataFormat } from "./types";

// Re-export the vega-loader functions to add TypeScript types

export function read(
  data: string | Record<string, unknown> | Array<Record<string, unknown>>,
  format:
    | DataFormat
    | {
        type: DataFormat["type"];
        parse: "auto";
      }
    | {
        type: DataFormat["type"];
        parse: FieldTypes;
      }
    | undefined,
): object[] {
  return vl.read(data, format);
}

export function createLoader(): {
  load: (
    url: string,
  ) => Promise<
    string | Record<string, unknown> | Array<Record<string, unknown>>
  >;
  http: (url: string) => Promise<string>;
} {
  return vl.loader();
}

export type VegaType =
  | "boolean"
  | "integer"
  | "number"
  | "date"
  | "string"
  | "unknown";

export type FieldTypes = Record<string, VegaType>;

export const typeParsers: Record<VegaType, (value: string) => unknown> =
  vl.typeParsers;
