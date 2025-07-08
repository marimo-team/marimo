/* Copyright 2024 Marimo. All rights reserved. */

// biome-ignore lint: preferObjectParams ok to ignore for common util
export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
