/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable react-hooks/rules-of-hooks */
import { useRef, useEffect } from "react";
import { dequal } from "dequal";
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
    Logger.debug(`[${name}] mounted`);
    return () => {
      Logger.debug(`[${name}] unmounted. Renders: ${renders.current}`);
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

    // If any props are deeply equal, we should warn about it
    const equalKeys = changedKeys.filter((key) => {
      return dequal(prevProps.current[key], props[key]);
    });

    if (changedKeys.length > 0) {
      Logger.debug(`[${name}] Props changed: ${changedKeys.join(", ")}`);
      if (equalKeys.length > 0) {
        Logger.debug(
          `[${name}] Props are deeply equal: ${equalKeys.join(", ")}`,
        );
      }
    }

    prevProps.current = props;
  });
}
