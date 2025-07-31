/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";

interface Props {
  seed: string;
  width: number;
  height: number;
}

// Simple hash function to convert a string to a number
const hashString = (str: string) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = Math.trunc(hash); // Convert to 32bit integer
  }
  return hash;
};

// Utility function to generate deterministic random heights based on a seed
const generateHeights = ({
  numBars,
  maxHeight,
  seed,
}: {
  numBars: number;
  maxHeight: number;
  seed: string;
}) => {
  const heights = [];
  let randomSeed = hashString(seed);
  for (let i = 0; i < numBars; i++) {
    randomSeed = (randomSeed * 9301 + 49_297) % 233_280;
    const random = randomSeed / 233_280;
    const height = Math.abs(Math.floor(random * maxHeight));
    heights.push(height);
  }
  return heights;
};

export const ChartSkeleton: React.FC<Props> = ({ seed, width, height }) => {
  const numBars = 9;
  const barWidth = width / numBars;
  const heights = generateHeights({ numBars, maxHeight: height - 15, seed });
  return (
    <div className="flex items-end gap-[1px] pb-2" style={{ width, height }}>
      {heights.map((barHeight, index) => (
        <div
          key={index}
          className="bg-[var(--slate-5)] animate-pulse"
          style={{ width: barWidth - 2, height: barHeight }}
        />
      ))}
    </div>
  );
};
