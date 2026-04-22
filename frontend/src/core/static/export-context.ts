/* Copyright 2026 Marimo. All rights reserved. */

export interface MarimoExportContext {
  trusted: true;
  notebookCode?: string;
}

declare global {
  interface Window {
    __MARIMO_EXPORT_CONTEXT__?: Readonly<MarimoExportContext>;
  }
}

function isMarimoExportContext(
  value: unknown,
): value is Readonly<MarimoExportContext> {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as MarimoExportContext;
  if (candidate.trusted !== true) {
    return false;
  }
  if (
    candidate.notebookCode !== undefined &&
    typeof candidate.notebookCode !== "string"
  ) {
    return false;
  }
  return true;
}

export function getMarimoExportContext():
  | Readonly<MarimoExportContext>
  | undefined {
  const context = window?.__MARIMO_EXPORT_CONTEXT__;
  return isMarimoExportContext(context) ? context : undefined;
}

export function hasTrustedExportContext(): boolean {
  return getMarimoExportContext()?.trusted === true;
}
