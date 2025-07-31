/* Copyright 2024 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import { type Milliseconds, Time } from "@/utils/time";

/**
 * Returns the elapsed time since mount, in milliseconds.
 */
export function useElapsedTime(initialStartTimeMs: Milliseconds) {
  const startTime = useRef(initialStartTimeMs);
  const [endTime, setEndTime] = useState(initialStartTimeMs);

  useEffect(() => {
    const step = 17; // 60 FPS
    const interval = setInterval(() => {
      // Need to use Date.now() here because
      // setInterval could be paused if the tab is inactive.
      setEndTime(Time.now().toMilliseconds());
    }, step);

    return () => clearInterval(interval);
  }, []);

  return endTime - startTime.current;
}
