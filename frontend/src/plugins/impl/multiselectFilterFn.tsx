/* Copyright 2024 Marimo. All rights reserved. */
export function multiselectFilterFn(option: string, value: string): number {
  const words = value.split(/\s+/);
  const match = words.every((word) =>
    option.toLowerCase().includes(word.toLowerCase()),
  );
  return match ? 1 : 0;
}
