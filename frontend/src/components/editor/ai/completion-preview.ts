/* Copyright 2026 Marimo. All rights reserved. */

export function captureSessionBaseline(
  existing: string | null,
  currentCode: string,
): string {
  return existing ?? currentCode;
}

export function codeToRestoreOnReject(opts: {
  hasPreviewed: boolean;
  baseline: string | null;
}): string | null {
  if (!opts.hasPreviewed || opts.baseline === null) {
    return null;
  }
  return opts.baseline;
}

export function shouldRestoreBeforeResubmit(hasPreviewed: boolean): boolean {
  return hasPreviewed;
}

export function originalCodeForMerge(opts: {
  hasPreviewed: boolean;
  baseline: string | null;
  currentCode: string;
}): string {
  if (opts.hasPreviewed && opts.baseline !== null) {
    return opts.baseline;
  }
  return opts.currentCode;
}
