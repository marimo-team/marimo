/* Copyright 2026 Marimo. All rights reserved. */

import type { CodeLensKind } from "./entities";

// Inline SVG markup mirroring the lucide icons used by the target panels:
// database (Data sources), hard-drive (Remote storage), database-zap (Cache).
const svg = (contents: string) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${contents}</svg>`;

const DATABASE = svg(
  '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 21 19V5"/><path d="M3 12A9 3 0 0 0 21 12"/>',
);
const HARD_DRIVE = svg(
  '<line x1="22" x2="2" y1="12" y2="12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><line x1="6" x2="6.01" y1="16" y2="16"/><line x1="10" x2="10.01" y1="16" y2="16"/>',
);
const DATABASE_ZAP = svg(
  '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5V19A9 3 0 0 0 15 21.84"/><path d="M21 5V8"/><path d="M21 12L18 17H22L19 22"/><path d="M3 12A9 3 0 0 0 14.59 14.87"/>',
);

export const LENS_ICONS: Record<CodeLensKind, string> = {
  table: DATABASE,
  connection: DATABASE,
  bucket: HARD_DRIVE,
  cache: DATABASE_ZAP,
};

export const LENS_TOOLTIPS: Record<CodeLensKind, string> = {
  table: "Open in data sources",
  connection: "Open in data sources",
  bucket: "Open in remote storage",
  cache: "Open cache panel",
};
