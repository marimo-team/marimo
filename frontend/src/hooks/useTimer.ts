/* Copyright 2024 Marimo. All rights reserved. */

import { useEffect, useRef, useState } from "react";
import useEvent from "react-use-event-hook";

/**
 * Creates a timer that counts returns the time in seconds.
 * Interval is 100ms.
 */
export function useTimer() {
  const [time, setTime] = useState(0);
  const interval = useRef<number>(undefined);

  const start = useEvent(() => {
    interval.current = window.setInterval(() => {
      setTime((time) => time + 0.1);
    }, 100);
  });

  const stop = useEvent(() => {
    if (interval.current != null) {
      window.clearInterval(interval.current);
      interval.current = undefined;
    }
  });

  const clear = useEvent(() => {
    setTime(0);
  });

  // Clear on unmount
  useEffect(() => {
    return () => {
      window.clearInterval(interval.current);
    };
  }, []);

  return {
    // one decimal place, exactly
    time: new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(time),
    start,
    stop,
    clear,
  };
}
