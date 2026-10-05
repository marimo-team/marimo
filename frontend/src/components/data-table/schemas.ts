/* Copyright 2026 Marimo. All rights reserved. */

import z from "zod";
import { rpc } from "@/plugins/core/rpc";

export type DownloadFormat = "csv" | "json" | "parquet" | "tsv" | "geojson";

/**
 * Per-request export options. Each field is optional. A missing field keeps
 * the widget's default for that setting.
 */
export interface DownloadAsOptions {
  separator?: string;
  encoding?: string;
  ensure_ascii?: boolean;
}

export interface DownloadAsRequest {
  format: DownloadFormat;
  options?: DownloadAsOptions;
  geometry_column?: string | null;
}

export type DownloadAsArgs = (req: DownloadAsRequest) => Promise<{
  url: string;
  filename: string;
  error?: string | null;
  missing_packages?: string[] | null;
  code?:
    | "geometry_required"
    | "invalid_geometry"
    | "invalid_metadata"
    | "unsupported_representation"
    | "unsupported_version"
    | "missing_packages"
    | "missing_crs"
    | "conversion_failed"
    | null;
  column?: string | null;
}>;

export const DownloadAsSchema = rpc
  .input(
    z.object({
      format: z.enum(["csv", "json", "parquet", "tsv", "geojson"]),
      geometry_column: z.string().nullish(),
      options: z
        .object({
          separator: z.string().optional(),
          encoding: z.string().optional(),
          ensure_ascii: z.boolean().optional(),
        })
        .optional(),
    }),
  )
  .output(
    z.object({
      url: z.string(),
      filename: z.string(),
      error: z.string().nullish(),
      missing_packages: z.array(z.string()).nullish(),
      code: z
        .enum([
          "geometry_required",
          "invalid_geometry",
          "invalid_metadata",
          "unsupported_representation",
          "unsupported_version",
          "missing_packages",
          "missing_crs",
          "conversion_failed",
        ])
        .nullish(),
      column: z.string().nullish(),
    }),
  );

const ExportMetadataSchema = z.object({
  geometry_columns: z.array(
    z.object({
      name: z.string(),
      encoding: z.enum(["objects", "wkb", "wkt", "other"]),
      crs: z.union([z.string(), z.record(z.string(), z.unknown())]).nullable(),
    }),
  ),
  primary_geometry_column: z.string().nullable(),
  default_geometry_column: z.string().nullable(),
  formats: z.record(
    z.string(),
    z.object({
      available: z.boolean(),
      reason: z.string().nullable(),
      missing_packages: z.array(z.string()),
    }),
  ),
});

export type ExportMetadata = z.infer<typeof ExportMetadataSchema>;
export type GetExportMetadata = (
  opts: Record<string, never>,
) => Promise<ExportMetadata>;

export const GetExportMetadataSchema = rpc
  .input(z.object({}))
  .output(ExportMetadataSchema);
