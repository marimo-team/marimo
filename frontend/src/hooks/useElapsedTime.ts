/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useState } from "react";

/**
 * Returns the elapsed time since mount.
 */
export function useElapsedTime() {
  const [time, setTime] = useState(0);

  useEffect(() => {
    const step = 17; // 60 FPS
    const interval = setInterval(() => {
      setTime((time) => time + step);
    }, step);

    return () => clearInterval(interval);
  });

  return time;
}
