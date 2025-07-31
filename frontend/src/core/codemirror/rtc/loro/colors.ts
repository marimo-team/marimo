/* Copyright 2024 Marimo. All rights reserved. */

export const COLORS = [
  "bg-[var(--amber-6)]",
  "bg-[var(--blue-6)]",
  "bg-[var(--crimson-6)]",
  "bg-[var(--cyan-6)]",
  "bg-[var(--grass-6)]",
  "bg-[var(--gray-6)]",
  "bg-[var(--green-6)]",
  "bg-[var(--lime-6)]",
  "bg-[var(--orange-6)]",
  "bg-[var(--purple-6)]",
  "bg-[var(--red-6)]",
  "bg-[var(--sage-6)]",
  "bg-[var(--sky-6)]",
  "bg-[var(--slate-6)]",
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
