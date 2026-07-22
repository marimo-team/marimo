/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";

export const LazyVegaEmbed = React.lazy(() =>
  import("./vega-embed-container").then((m) => ({
    default: m.VegaEmbedContainer,
  })),
);
