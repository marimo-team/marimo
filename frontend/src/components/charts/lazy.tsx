/* Copyright 2026 Marimo. All rights reserved. */

import React from "react";

export const LazyVegaEmbed = React.lazy(() =>
  import("react-vega").then((m) => ({ default: m.VegaEmbed })),
);
