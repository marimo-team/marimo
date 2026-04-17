/* Copyright 2026 Marimo. All rights reserved. */

import z from "zod";
import { rpc } from "@/plugins/core/rpc";

export type DownloadAsArgs = (req: {
  format: "csv" | "json" | "parquet";
}) => Promise<{
  url: string;
  filename: string;
  error?: string | null;
  missing_packages?: string[] | null;
}>;

export const DownloadAsSchema = rpc
  .input(
    z.object({
      format: z.enum(["csv", "json", "parquet"]),
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
