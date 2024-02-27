/* Copyright 2024 Marimo. All rights reserved. */
import { Milliseconds, Time } from "@/utils/time";
import { useEffect, useRef, useState } from "react";

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
