/* Copyright 2024 Marimo. All rights reserved. */

import type { Theme } from "@glideapps/glide-data-grid";
import type { ResolvedTheme } from "@/theme/useTheme";

export function getGlideTheme(
  theme: ResolvedTheme,
): Partial<Theme> | undefined {
  if (theme === "light") {
    return {
      lineHeight: 1.25,
    };
  }

  return {
    lineHeight: 1.25,
    accentColor: "#7c3aed",
    accentLight: "rgba(124, 58, 237, 0.15)",

    textDark: "#f4f4f5",
    textMedium: "#a1a1aa",
    textLight: "#71717a",
    textBubble: "#f4f4f5",

    bgIconHeader: "#a1a1aa",
    fgIconHeader: "#18181b",
    textHeader: "#d4d4d8",
    textHeaderSelected: "#18181b",

    bgCell: "#18181b",
    bgCellMedium: "#27272a",
    bgHeader: "#27272a",
    bgHeaderHasFocus: "#3f3f46",
    bgHeaderHovered: "#3f3f46",

    bgBubble: "#27272a",
    bgBubbleSelected: "#7c3aed",

    bgSearchResult: "#312e81",

    borderColor: "#27272a",
    drilldownBorder: "#7c3aed",

    linkColor: "#818cf8",

    headerFontStyle: "bold 14px",
    baseFontStyle: "13px",
  };
}
