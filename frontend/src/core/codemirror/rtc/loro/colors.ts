/* Copyright 2026 Marimo. All rights reserved. */

export const COLORS = [
  "bg-(--amber-6)",
  "bg-(--blue-6)",
  "bg-(--crimson-6)",
  "bg-(--cyan-6)",
  "bg-(--grass-6)",
  "bg-(--gray-6)",
  "bg-(--green-6)",
  "bg-(--lime-6)",
  "bg-(--orange-6)",
  "bg-(--purple-6)",
  "bg-(--red-6)",
  "bg-(--sage-6)",
  "bg-(--sky-6)",
  "bg-(--slate-6)",
] as const;

/**
 * Get a deterministic color from a string or number.
 * @param input - The input to get a color from.
 */
export const getColor = (input: string | number) => {
  if (typeof input === "string") {
    // Create a simple hash from the string
    let hash = 0;
    for (let i = 0; i < input.length; i++) {
      hash = (hash << 5) - hash + input.charCodeAt(i);
      hash = Math.trunc(hash); // Convert to 32bit integer
    }
    // Use absolute value to ensure positive index
    return COLORS[Math.abs(hash) % COLORS.length];
  }

  // Fallback for number input
  return COLORS[input % COLORS.length];
};
