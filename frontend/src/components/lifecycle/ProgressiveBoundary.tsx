/* Copyright 2026 Marimo. All rights reserved. */

import { type Atom, useAtomValue } from "jotai";
import type React from "react";
import { type PropsWithChildren, useEffect, useState } from "react";

interface Props {
  /** Children render once this atom resolves true. */
  requires: Atom<boolean>;
  fallback?: React.ReactNode;
  /** Suppress the fallback for this many ms; avoids spinner flashes. */
  delay?: number;
}

/**
 * ```tsx
 * <ProgressiveBoundary requires={canPaintAtom} delay={2000} fallback={<Spinner />}>
 *   <Editor />
 * </ProgressiveBoundary>
 * ```
 */
export const ProgressiveBoundary: React.FC<PropsWithChildren<Props>> = ({
  requires,
  fallback = null,
  delay = 0,
  children,
}) => {
  const ready = useAtomValue(requires);

  const [delayElapsed, setDelayElapsed] = useState(delay <= 0);
  useEffect(() => {
    if (delay <= 0) {
      setDelayElapsed(true);
      return;
    }
    setDelayElapsed(false);
    const t = setTimeout(() => setDelayElapsed(true), delay);
    return () => clearTimeout(t);
  }, [delay]);

  if (ready) {
    return children;
  }
  if (!delayElapsed) {
    return null;
  }
  return fallback;
};
