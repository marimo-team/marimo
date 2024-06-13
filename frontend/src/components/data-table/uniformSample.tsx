/* Copyright 2024 Marimo. All rights reserved. */

/**
 * Uniformly sample n items from an array
 */
export function uniformSample<T>(items: T[], n: number): T[] {
  if (items.length <= n) {
    return items;
  }
  const sample: T[] = [];
  const step = items.length / n;
  for (let i = 0; i < n - 1; i++) {
    const idx = Math.floor(i * step);
    sample.push(items[idx]);
  }
  const last = items.at(-1) as T;
  sample.push(last);
  return sample;
}
