/* Copyright 2026 Marimo. All rights reserved. */

/**
 * Returns CSS class names for vega container sizing.
 *
 * Vega-embed sets .vega-embed to display:inline-block, so it collapses
 * to content width by default. When the spec uses width/height "container",
 * vega measures the container via containerSize(). These classes set
 * width/height: 100% on .vega-embed so that measurement returns a real value.
 */
export function vegaContainerClasses(spec: object): {
  "vega-container-width"?: boolean;
  "vega-container-height"?: boolean;
} {
  return {
    "vega-container-width": "width" in spec && spec.width === "container",
    "vega-container-height": "height" in spec && spec.height === "container",
  };
}
