/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */

import { dequal } from "dequal";
import { useEffect, useMemo, useRef } from "react";
import { Logger } from "@/utils/Logger";

/**
 * Logs when a component is mounted and unmounted.
 * Only runs in development mode.
 */
export function useDebugMounting(name: string) {
  if (process.env.NODE_ENV !== "development") {
    return;
  }

  const renders = useRef(0);

  useEffect(() => {
    Logger.debug(`🐛 [${name}] mounted`);
    return () => {
      Logger.debug(`🐛 [${name}] unmounted. Renders: ${renders.current}`);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    renders.current += 1;
    Logger.debug(`[${name}] rendered: ${renders.current}`);
  });
}

/**
 * Logs when a component's props change.
 * Only runs in development mode.
 */
export function usePropsDidChange(
  name: string,
  props: Record<string, unknown>,
) {
  if (process.env.NODE_ENV !== "development") {
    return;
  }

  const prevProps = useRef(props);

  useEffect(() => {
    const keys = Object.keys(props);
    const changedKeys = keys.filter((key) => {
      return prevProps.current[key] !== props[key];
    });

    const equalKeys = changedKeys.filter((key) => {
      return dequal(prevProps.current[key], props[key]);
    });

    if (changedKeys.length > 0) {
      Logger.debug(`[${name}] Props changed: ${changedKeys.join(", ")}`);

      // If all changed keys are deeply equal, we should warn about it
      if (equalKeys.length === changedKeys.length) {
        Logger.debug(
          `[${name}] ⚠️ Props are deeply equal: ${equalKeys.join(", ")}`,
        );
      }
    }

    prevProps.current = props;
  });
}

/**
 * Like useMemo, but logs when the value changes.
 */
export function useMemoDebugChanges<T>(
  name: string,
  fn: () => T,
  deps: unknown[],
) {
  if (process.env.NODE_ENV !== "development") {
    return fn();
  }

  const previousDeps = useRef<unknown[]>([]);

  return useMemo(() => {
    if (previousDeps.current.length === 0) {
      previousDeps.current = deps;
      return fn();
    }

    const changedIndices: number[] = [];
    const changedDeps = deps.filter((dep, idx) => {
      if (!dequal(dep, previousDeps.current[idx])) {
        changedIndices.push(idx);
        return true;
      }
      return false;
    });

    if (changedDeps.length > 0) {
      Logger.debug(
        `[${name}] Memo deps changed at indices: ${changedIndices}`,
        {
          previous: previousDeps.current,
          current: deps,
        },
      );
    }

    previousDeps.current = deps;

    return fn();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
