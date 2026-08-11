/* Copyright 2026 Marimo. All rights reserved. */
import React from "react";
import {
  MAX_PROFILER_EVENTS,
  profilerEventsAtom,
  profilingEnabledAtom,
} from "./atoms";
import { store } from "@/core/state/jotai";

/**
 * Measures subtree render durations when profiling is enabled. Renders a plain
 * fragment otherwise, so the gate-off path has no Profiler overhead.
 */
export const ProfilingWrapper: React.FC<{
  name: string;
  children: React.ReactNode;
}> = ({ name, children }) => {
  if (!store.get(profilingEnabledAtom)) {
    return children;
  }

  return (
    <React.Profiler
      id={name}
      onRender={(id, phase, actualDuration, baseDuration) => {
        store.set(profilerEventsAtom, (prev) => {
          const next = [
            ...prev,
            {
              id,
              phase,
              actualDuration,
              baseDuration,
              timestamp: performance.now(),
            },
          ];
          return next.length > MAX_PROFILER_EVENTS
            ? next.slice(-MAX_PROFILER_EVENTS)
            : next;
        });
      }}
    >
      {children}
    </React.Profiler>
  );
};
