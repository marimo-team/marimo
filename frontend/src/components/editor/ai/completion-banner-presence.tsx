/* Copyright 2026 Marimo. All rights reserved. */

import { useEffect, useRef, useState, type ReactNode } from "react";

import "./completion-banner-presence.css";

/** Keep departing controls inert until the browser finishes their transitions. */
export function CompletionBannerPresence({
  open,
  children,
}: {
  open: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [present, setPresent] = useState(open);

  useEffect(() => {
    if (open) {
      setPresent(true);
      return;
    }
    if (!present) {
      return;
    }

    // Only inspect the closing wrapper, never measure inactive notebook cells.
    const transitions = ref.current?.getAnimations?.() ?? [];
    if (transitions.length === 0) {
      setPresent(false);
      return;
    }

    let cancelled = false;
    void Promise.allSettled(
      transitions.map((transition) => transition.finished),
    ).then(() => {
      if (!cancelled) {
        setPresent(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [open, present]);

  return (
    <div
      ref={ref}
      data-state={open ? "open" : "closed"}
      inert={!open}
      aria-hidden={!open}
      className="completion-banner-presence w-full bg-(--cm-background)"
    >
      <div className="min-h-0 overflow-hidden flex justify-center">
        {(open || present) && children}
      </div>
    </div>
  );
}
