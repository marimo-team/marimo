/* Copyright 2024 Marimo. All rights reserved. */
import type { VegaLiteSpec } from "./types";
import { asRemoteURL } from "@/core/runtime/config";

/**
 * If the URL in the data-spec if relative, we need to fix it to be absolute,
 * otherwise vega-lite throws an error.
 */
export function fixRelativeUrl(spec: VegaLiteSpec) {
  if (spec.data && "url" in spec.data) {
    spec.data.url = asRemoteURL(spec.data.url).href;
  }
  return spec;
}
