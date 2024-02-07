/* Copyright 2024 Marimo. All rights reserved. */

import { asURL } from "@/utils/url";
import { VegaLiteSpec } from "./types";

/**
 * If the URL in the data-spec if relative, we need to fix it to be absolute,
 * otherwise vega-lite throws an error.
 */
export function fixRelativeUrl(spec: VegaLiteSpec) {
  if (spec.data && "url" in spec.data) {
    spec.data.url = asURL(spec.data.url).href;
  }
  return spec;
}
