/* Copyright 2023 Marimo. All rights reserved. */

export function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}
