/* Copyright 2026 Marimo. All rights reserved. */

import { z } from "zod";

/**
 * 'alert' is deprecated. Use 'danger' instead.
 */
export type Intent =
  | "neutral"
  | "success"
  | "warn"
  | "danger"
  | "info"
  | "alert";
export const zodIntent = z
  // 'alert' is deprecated. Use 'danger' instead.
  .enum(["neutral", "success", "warn", "danger", "info", "alert"])
  .default("neutral");
