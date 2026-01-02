/* Copyright 2026 Marimo. All rights reserved. */

import { useMemo } from "react";
import {
  getIframeCapabilities,
  type IframeCapabilities,
} from "@/utils/capabilities";

/**
 * React hook to access iframe capabilities
 */
export function useIframeCapabilities(): IframeCapabilities {
  return useMemo(() => getIframeCapabilities(), []);
}
