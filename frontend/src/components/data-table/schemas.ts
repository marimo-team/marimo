/* Copyright 2026 Marimo. All rights reserved. */

import z from "zod";
import { rpc } from "@/plugins/core/rpc";
import type { ResolvedExportLocale } from "./export-locale";

export type DownloadAsArgs = (req: {
  format: "csv" | "json" | "parquet" | "tsv";
  locale?: ResolvedExportLocale;
}) => Promise<{
  url: string;
  filename: string;
  error?: string | null;
  missing_packages?: string[] | null;
}>;

export const DownloadAsSchema = rpc
  .input(
    z.object({
      format: z.enum(["csv", "json", "parquet", "tsv"]),
      locale: z
        .object({
          tag: z.string(),
          decimal_separator: z.string(),
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
    }),
  );
