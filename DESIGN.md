---
version: alpha
name: marimo
description: Design system for marimo, a reactive Python notebook for reproducible, git-friendly, deployable work.
colors:
  background: "#FFFFFF"
  background-dark: "#181C1A"
  foreground: "#0F172A"
  foreground-dark: "#ECEEED"
  surface-muted: "#F1F5F9"
  surface-muted-dark: "#020303"
  muted-foreground: "#64748B"
  muted-foreground-dark: "#AAB2AF"
  popover: "#FFFFFF"
  popover-dark: "#252927"
  popover-foreground: "#0F172A"
  popover-foreground-dark: "#AAB2AF"
  card: "#FFFFFF"
  card-dark: "#252927"
  card-foreground: "#0F172A"
  card-foreground-dark: "#C0C6C3"
  border: "#E2E8F0"
  border-dark: "#3B403E"
  input: "#A3A3A3"
  input-dark: "#474C4A"
  primary: "#0880EA"
  primary-dark: "#28879F"
  on-primary: "#F8FAFC"
  on-primary-dark: "#B6ECF7"
  secondary: "#F1F5F9"
  secondary-dark: "#ECEEED"
  on-secondary: "#0F172A"
  on-secondary-dark: "#252927"
  accent: "#EDF6FF"
  accent-dark: "#1D5B6A"
  on-accent: "#0B68CB"
  on-accent-dark: "#B6ECF7"
  ring: "#94A3B8"
  destructive: "#FF6666"
  on-destructive: "#F8FAFC"
  error: "#EA5D5D"
  on-error: "#F8FAFC"
  success: "#66FF7F"
  on-success: "#F8FAFC"
  action: "#FEF2A5"
  action-hover: "#FFF8BB"
  on-action: "#946800"
  link: "#0B68CB"
  link-dark: "#479BF5"
  link-visited: "#8E4EC6"
  link-visited-dark: "#BF9BDF"
  stale: "#EBE2CC"
  stale-dark: "#3E3720"
  code-background: "#FFFFFF"
  code-background-dark: "#282C34"
  surface: "#FFFFFF"
  surface-dark: "#252927"
  data-grid-accent: "#7C3AED"
typography:
  body-md:
    fontFamily: PT Sans
    fontSize: 1rem
    fontWeight: "400"
    lineHeight: 1.75rem
    letterSpacing: 0em
  body-sm:
    fontFamily: PT Sans
    fontSize: 0.875rem
    fontWeight: "400"
    lineHeight: 1.25rem
    letterSpacing: 0em
  label-md:
    fontFamily: PT Sans
    fontSize: 0.875rem
    fontWeight: "500"
    lineHeight: "1"
    letterSpacing: 0em
  label-xs:
    fontFamily: PT Sans
    fontSize: 0.75rem
    fontWeight: "600"
    lineHeight: 1rem
    letterSpacing: 0em
  markdown-heading:
    fontFamily: Lora
    fontSize: 1.875rem
    fontWeight: "600"
    lineHeight: 2.25rem
    letterSpacing: -0.025em
  code-editor:
    fontFamily: Fira Mono
    fontSize: 14px
    fontWeight: "400"
    lineHeight: 1.25rem
    letterSpacing: 0em
  slide-h1:
    fontFamily: PT Sans
    fontSize: 4.375rem
    fontWeight: "600"
    lineHeight: "1.2"
    letterSpacing: 0em
rounded:
  sm: 4px
  DEFAULT: 8px
  md: 6px
  lg: 8px
  cell: 10px
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 0.5rem
  xs: 0.25rem
  sm: 0.5rem
  md: 1rem
  lg: 1.5rem
  xl: 3rem
  content-compact: 740px
  content-medium: 1110px
  content-wide: 1400px
  grid-row-height: 20px
  grid-columns: "24"
components:
  app-shell:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.body-md}"
  cell:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    typography: "{typography.body-md}"
    rounded: "{rounded.cell}"
    width: 100%
  output-area:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    typography: "{typography.body-md}"
    padding: 1rem
    width: 100%
  code-editor:
    backgroundColor: "{colors.code-background}"
    textColor: "{colors.foreground}"
    typography: "{typography.code-editor}"
    width: 100%
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    height: 2.25rem
  button-action:
    backgroundColor: "{colors.action}"
    textColor: "{colors.on-action}"
    typography: "{typography.label-md}"
    rounded: "{rounded.md}"
    height: 2.25rem
  input:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.code-editor}"
    rounded: "{rounded.sm}"
    height: 1.5rem
  data-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    typography: "{typography.body-sm}"
    width: 100%
---

## Brand Assets

- Logo SVG: https://raw.githubusercontent.com/marimo-team/marimo/main/docs/_static/marimo-logotype-thick.svg
- Preserve the original aspect ratio.
- Do not recolor unless explicitly requested.

## Visual Character

- Compact, software-native, and utilitarian.
- White or near-black work surfaces with slate borders and muted secondary text.
- Restrained blue for primary interaction; yellow for action, stale, or needs-run states.
- Avoid decorative gradients, marketing-style heroes, nested cards, and one-off palettes.

## Color

- Use background, surface, foreground, border, and muted tokens for structure.
- Use primary for primary actions, selection, progress, and clear focus only.
- Use action and stale colors for manual action or freshness state, not generic warning.
- Use destructive, error, and success colors only for their semantic states.
- Preserve light and dark token pairs whenever a color appears in both modes.

## Typography

- Use PT Sans for UI and prose, Lora for authored markdown headings, and Fira Mono for code-like values.
- Keep control text compact and legible.
- Do not add viewport-based type scaling beyond marimo's app defaults.

## Surfaces

- Use borders first and subtle shadows second.
- Cells, outputs, editors, markdown, tables, and data grids should be full-width and overflow-safe.
- Keep data UI dense and inspectable: stable columns, predictable overflow, readable headers, and no decorative framing around tables or charts.
- Cards are for repeated items, dialogs, or genuinely framed tools; do not style page sections as cards.

## Components

- Buttons should be compact, label-like, focusable, and drawn from primary, secondary, or action semantics.
- Icon buttons should use familiar existing icons and tooltips for unclear actions.
- Inputs, selects, and textareas should be compact, bordered, readable, and use code typography only for code-like values.
- Tabs, menus, popovers, dialogs, and tooltips should use semantic surfaces, borders, focus states, and restrained shadow.
- Runtime states should pair color with labels, icons, borders, position, or shape.

## Motion

Use short transitions for hover, focus, loading, resize, drag, and stale-output changes. Avoid decorative animation.
