/* Copyright 2023 Marimo. All rights reserved. */

import { z } from "zod";

export type Intent = "neutral" | "success" | "warn" | "danger" | "info";
export const zodIntent = z
  .enum(["neutral", "success", "warn", "danger", "info"])
  .default("neutral");
