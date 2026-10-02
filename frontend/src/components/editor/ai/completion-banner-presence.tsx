/* Copyright 2026 Marimo. All rights reserved. */

import { Collapsible } from "radix-ui";
import type { ReactNode } from "react";

import "./completion-banner-presence.css";

/** Keep departing controls inert while Radix waits for the exit animation. */
export function CompletionBannerPresence({
  open,
  children,
}: {
  open: boolean;
  children: ReactNode;
}) {
  return (
    <Collapsible.Root open={open}>
      <Collapsible.Content
        inert={!open}
        aria-hidden={!open}
        className="completion-banner-presence w-full bg-(--cm-background) flex justify-center overflow-hidden"
      >
        {children}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
