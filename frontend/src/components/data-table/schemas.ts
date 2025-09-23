/* Copyright 2024 Marimo. All rights reserved. */

import z from "zod";
import { rpc } from "@/plugins/core/rpc";

export type DownloadAsArgs = (req: {
  format: "csv" | "json" | "parquet";
}) => Promise<string>;

export const DownloadAsSchema = rpc
  .input(
    z.object({
      format: z.enum(["csv", "json", "parquet"]),
    }),
  )
  .output(z.string());
