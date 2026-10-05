/* Copyright 2026 Marimo. All rights reserved. */
import type React from "react";

type ViewerStyle = React.CSSProperties & Record<`--w-rjv-${string}`, string>;

const BASE_THEME: ViewerStyle = {
  fontSize: "var(--text-xs, .75rem)",
  lineHeight: "var(--text-xs--line-height, 1rem)",
  "--w-rjv-font-family": "monospace",
  "--w-rjv-background-color": "transparent",
  "--w-rjv-key-string": "var(--w-rjv-color)",
  "--w-rjv-arrow-color": "var(--w-rjv-color)",
  "--w-rjv-curlybraces-color": "var(--w-rjv-color)",
  "--w-rjv-colon-color": "var(--w-rjv-color)",
  "--w-rjv-brackets-color": "var(--w-rjv-color)",
  "--w-rjv-quotes-color": "var(--w-rjv-color)",
  "--w-rjv-ellipsis-color": "var(--w-rjv-type-string-color)",
  "--w-rjv-quotes-string-color": "var(--w-rjv-type-string-color)",
  "--w-rjv-type-bigint-color": "var(--w-rjv-type-int-color)",
  "--w-rjv-type-url-color": "var(--link)",
  "--w-rjv-type-nan-color": "var(--w-rjv-type-null-color)",
};

export const marimoLightTheme: ViewerStyle = {
  ...BASE_THEME,
  "--w-rjv-color": "#002b36",
  "--w-rjv-key-number": "#6c71c4",
  "--w-rjv-line-color": "rgb(235, 235, 235)",
  "--w-rjv-info-color": "rgba(0, 0, 0, 0.3)",
  "--w-rjv-type-string-color": "#cb4b16",
  "--w-rjv-type-int-color": "#268bd2",
  "--w-rjv-type-float-color": "#859900",
  "--w-rjv-type-boolean-color": "#2aa198",
  "--w-rjv-type-date-color": "#586e75",
  "--w-rjv-type-null-color": "#d33682",
  "--w-rjv-type-undefined-color": "#586e75",
};

export const marimoDarkTheme: ViewerStyle = {
  ...BASE_THEME,
  "--w-rjv-color": "#f8f8f8",
  "--w-rjv-key-number": "#86c1b9",
  "--w-rjv-line-color": "#383838",
  "--w-rjv-info-color": "#b8b8b8",
  "--w-rjv-type-string-color": "#dc9656",
  "--w-rjv-type-int-color": "#a16946",
  "--w-rjv-type-float-color": "#a1b56c",
  "--w-rjv-type-boolean-color": "#ba8baf",
  "--w-rjv-type-date-color": "#7cafc2",
  "--w-rjv-type-null-color": "#ab4642",
  "--w-rjv-type-undefined-color": "#d8d8d8",
};
