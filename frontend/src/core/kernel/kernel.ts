/* Copyright 2024 Marimo. All rights reserved. */
import { Logger } from "../../utils/Logger";

export function getKernelId(): string | null {
  if (typeof window === "undefined") {
    Logger.warn("getKernelId() called without window");
    return null;
  }

  return new URLSearchParams(window.location.search).get("kernel_id");
}
