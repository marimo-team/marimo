/* Copyright 2026 Marimo. All rights reserved. */

import React, { useEffect, useState } from "react";
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

function getGlidePortalContainer(): Element {
  return document.fullscreenElement ?? document.body;
}

function useGlidePortalContainer(): Element {
  const [container, setContainer] = useState<Element>(getGlidePortalContainer);

  useEffect(() => {
    const handleFullscreenChange = () => {
      if (document.fullscreenElement) {
        setContainer(document.fullscreenElement);
      } else {
        dismissGlideOverlay();
        setContainer(document.body);
      }
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    // Sync on mount in case fullscreen became active before this editor mounted.
    handleFullscreenChange();

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, []);

  return container;
}

/**
 * Per-instance Glide Data Grid overlay portal on document.body.
 * Moves into the active fullscreen element via createPortal so edit overlays stay visible
 */
export function GlideDataEditorPortal({
  portalRef,
}: {
  portalRef: React.RefObject<HTMLDivElement | null>;
}) {
  const container = useGlidePortalContainer();

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
    container,
  );
}
