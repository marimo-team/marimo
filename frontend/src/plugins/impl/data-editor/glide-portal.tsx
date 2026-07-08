/* Copyright 2026 Marimo. All rights reserved. */

import React, { useEffect } from "react";
import { createPortal } from "react-dom";

/**
 * Dismiss any open Glide Data Grid overlay by firing Escape on it.
 */
export function dismissGlideOverlay() {
  const overlay = document.querySelector(
    "[data-testid='glide-data-editor-portal'] .gdg-clip-region",
  );
  if (overlay) {
    overlay.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
  }
}

function useGlidePortalFullscreen(
  portalRef: React.RefObject<HTMLDivElement | null>,
) {
  useEffect(() => {
    const handleFullscreenChange = () => {
      const portal = portalRef.current;
      if (!portal) {
        return;
      }

      const fullscreenElement = document.fullscreenElement;
      if (fullscreenElement) {
        fullscreenElement.appendChild(portal);
      } else {
        dismissGlideOverlay();
        document.body.appendChild(portal);
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    handleFullscreenChange();

    const portal = portalRef.current;

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      if (portal && portal.parentElement !== document.body) {
        document.body.appendChild(portal);
      }
    };
  }, [portalRef]);
}

/**
 * Per-instance Glide Data Grid overlay portal on document.body.
 * Reparents into the active fullscreen element so edit overlays stay visible.
 */
export function GlideDataEditorPortal({
  portalRef,
}: {
  portalRef: React.RefObject<HTMLDivElement | null>;
}) {
  useGlidePortalFullscreen(portalRef);

  return createPortal(
    <div
      ref={portalRef}
      data-testid="glide-data-editor-portal"
      style={{
        position: "fixed",
        left: 0,
        top: 0,
        zIndex: 9999,
      }}
    />,
    document.body,
  );
}
