/* Copyright 2026 Marimo. All rights reserved. */
import { useEffect } from "react";
import { useEvent } from "@/hooks/useEvent";
import { Logger } from "@/utils/Logger";

/**
 * The Keyboard Lock API (`navigator.keyboard`) lets us capture Escape while in
 * native fullscreen instead of the browser eagerly exiting on the first press.
 * It's Chromium-only and may reject (e.g. insecure context); the DOM lib does
 * not type it, so we declare the minimal surface we use.
 */
interface KeyboardLock {
  lock?: (keyCodes?: string[]) => Promise<void>;
  unlock?: () => void;
}

function getKeyboardLock(): KeyboardLock | undefined {
  return (navigator as Navigator & { keyboard?: KeyboardLock }).keyboard;
}

interface UseFullscreenEscapeOptions {
  enabled?: boolean;
  /** Escape is only intercepted while this element (or a descendant) is the
   * document's fullscreen element. */
  getElement: () => Element | null | undefined;
  /**
   * Return `true` to keep fullscreen (the callback owns any `preventDefault` /
   * `stopImmediatePropagation`); `false` lets the hook exit.
   */
  onEscape?: (event: KeyboardEvent) => boolean;
}

/**
 * Locks Escape while the owned element is fullscreen and routes it through
 * `onEscape`, so a single press doesn't eagerly exit (jarring mid-interaction).
 * App-specific routing lives in `onEscape`. Falls back to the browser's native
 * single-press exit where the Keyboard Lock API is unavailable.
 */
export function useFullscreenEscape({
  enabled = true,
  getElement,
  onEscape,
}: UseFullscreenEscapeOptions): void {
  const isOwnedFullscreen = useEvent(() => {
    const fullscreenEl = document.fullscreenElement;
    const element = getElement();
    // True when our element is the fullscreen element or contains it. We
    // deliberately don't match when an *ancestor* is fullscreen, so an
    // unrelated whole-page fullscreen doesn't hijack Escape.
    return (
      fullscreenEl != null && element != null && element.contains(fullscreenEl)
    );
  });
  const handleEscape = useEvent(
    (event: KeyboardEvent) => onEscape?.(event) === true,
  );

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const keyboard = getKeyboardLock();

    const handleFullscreenChange = () => {
      if (isOwnedFullscreen()) {
        keyboard?.lock?.(["Escape"]).catch(() => {
          // Unsupported or denied: native single-press exit remains in effect.
          Logger.debug("Keyboard lock not supported or denied");
        });
      } else {
        keyboard?.unlock?.();
      }
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || event.repeat || !isOwnedFullscreen()) {
        return;
      }
      if (handleEscape(event)) {
        return;
      }
      // The callback declined: exit fullscreen ourselves (the keyboard lock
      // suppressed the native exit) and stop other listeners from also acting.
      event.preventDefault();
      event.stopImmediatePropagation();
      void document.exitFullscreen().catch((error) => {
        Logger.error("Failed to exit fullscreen", error);
      });
    };

    // Acquire the lock if we mount while already fullscreen; no
    // `fullscreenchange` event fires in that case.
    handleFullscreenChange();

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      window.removeEventListener("keydown", handleKeyDown, { capture: true });
      keyboard?.unlock?.();
    };
  }, [enabled, isOwnedFullscreen, handleEscape]);
}
