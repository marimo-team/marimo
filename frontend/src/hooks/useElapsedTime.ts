/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import { type Milliseconds, Time } from "@/utils/time";

/**
 * Returns the elapsed time since mount, in milliseconds.
 */
export function useElapsedTime(initialStartTimeMs: Milliseconds): Milliseconds {
  const startTime = useRef(initialStartTimeMs);
  const [endTime, setEndTime] = useState(initialStartTimeMs);

  useEffect(() => {
    // The live timer displays tenths of a second. Updating it at animation-frame
    // speed would needlessly re-render every running cell.
    const step = 100;
    const interval = setInterval(() => {
      // Need to use Date.now() here because
      // setInterval could be paused if the tab is inactive.
      setEndTime(Time.now().toMilliseconds());
    }, step);

    return () => clearInterval(interval);
  }, []);

  return (endTime - startTime.current) as Milliseconds;
}
