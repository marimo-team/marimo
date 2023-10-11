/* Copyright 2023 Marimo. All rights reserved. */

import { VegaLiteSpec } from "./types";

/**
 * If the URL in the data-spec if relative, we need to fix it to be absolute,
 * otherwise vega-lite throws an error.
 */
export function fixRelativeUrl(spec: VegaLiteSpec) {
  if (spec.data && "url" in spec.data && spec.data.url.startsWith("/")) {
    spec.data.url = `${window.location.origin}${spec.data.url}`;
  }
  return spec;
}
