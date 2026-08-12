/* Copyright 2026 Marimo. All rights reserved. */

import { useRef } from "react";
import type { VegaEmbedProps } from "react-vega";
import { VegaEmbed } from "react-vega";
import { useVegaContainerRemeasure } from "@/plugins/impl/vega/use-vega-container-remeasure";
import { getContainerWidth } from "@/plugins/impl/vega/utils";

/**
 * VegaEmbed that remeasures width:"container" charts when their host gains size
 * (e.g. after a display:none parent becomes visible).
 */
export function VegaEmbedContainer(props: VegaEmbedProps) {
  const ref = useRef<HTMLDivElement>(null);
  const enabled = getContainerWidth(props.spec) === "container";
  useVegaContainerRemeasure(ref, enabled);
  return <VegaEmbed ref={ref} {...props} />;
}
