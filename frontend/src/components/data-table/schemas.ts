/* Copyright 2026 Marimo. All rights reserved. */

import z from "zod";
import { rpc } from "@/plugins/core/rpc";

export type DownloadAsArgs = (req: {
  format: "csv" | "json" | "parquet";
}) => Promise<{ url: string; filename: string }>;

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
    }),
  );
