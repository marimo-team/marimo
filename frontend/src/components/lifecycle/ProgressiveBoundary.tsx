/* Copyright 2026 Marimo. All rights reserved. */

import { type Atom, useAtomValue } from "jotai";
import type React from "react";
import type { PropsWithChildren } from "react";
import { useDelayElapsed } from "@/hooks/useDelayElapsed";

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
  // Key the delay off `ready` so the suppression window re-arms whenever the
  // gate closes again — otherwise a `true → false` flip would show the
  // fallback immediately and reintroduce the flash `delay` is meant to avoid.
  const delayElapsed = useDelayElapsed(ready ? 0 : delay);

  if (ready) {
    return children;
  }
  if (!delayElapsed) {
    return null;
  }
  return fallback;
};
