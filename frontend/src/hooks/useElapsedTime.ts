/* Copyright 2023 Marimo. All rights reserved. */
import { useEffect, useRef, useState } from "react";

/**
 * Returns the elapsed time since mount, in milliseconds.
 */
export function useElapsedTime() {
  const startTime = useRef(Date.now());
  const [endTime, setEndTime] = useState(Date.now());

  useEffect(() => {
    const step = 17; // 60 FPS
    const interval = setInterval(() => {
      // Need to use Date.now() here because
      // setInterval could be paused if the tab is inactive.
      setEndTime(Date.now());
    }, step);

    return () => clearInterval(interval);
  });

  return endTime - startTime.current;
}
