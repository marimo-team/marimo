/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Returns CSS class names for vega container sizing.
 *
 * Vega-embed sets .vega-embed to display:inline-block, so it collapses
 * to content width by default. When the spec uses width "container",
 * vega measures the container via containerSize(). This class sets
 * width: 100% on .vega-embed so that measurement returns a real value.
 *
 * Note: height "container" is not supported because block elements have
 * no intrinsic height — the container collapses to 0 without an explicit
 * height set somewhere in the parent chain.
 */
export function vegaContainerClasses(spec: object): {
  "vega-container-width"?: boolean;
} {
  return {
    "vega-container-width": "width" in spec && spec.width === "container",
  };
}
