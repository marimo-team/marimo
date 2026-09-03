/* Copyright 2026 Marimo. All rights reserved. */

import type { PointerEvent as ReactPointerEvent } from "react";

export interface Size {
  width: number;
  height: number;
}

export interface Position {
  x: number;
  y: number;
}

interface StyledPosition {
  x: number | string;
  y: number | string;
}

export type FloatingCorner =
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right";
export type ResizeCorner = FloatingCorner;

interface PointerGestureCallbacks {
  onCancel: () => void;
  onFinish: (event: PointerEvent, didMove: boolean) => void;
  onMove: (event: PointerEvent) => void;
  onStart: () => void;
}

const DEFAULT_FLOATING_WIDTH = 360;
const DEFAULT_ASPECT_RATIO = 16 / 9;
const MIN_FLOATING_WIDTH = 200;
const MAX_FLOATING_WIDTH = 720;
const FLOATING_MARGIN = 16;
const MOVE_THRESHOLD = 5;
const FLICK_VELOCITY_THRESHOLD = 0.5;
const FLICK_PROJECTION_MS = 180;
const CAPTURE_EVENT_OPTIONS = { capture: true } as const;

export const RESIZE_HIT_TARGET_SIZE = 11;
export const NATIVE_CONTROLS_HEIGHT = 48;

export const getInitialFloatingSize = (inlineSize: Size | null): Size => {
  const aspectRatio =
    inlineSize && inlineSize.height > 0
      ? inlineSize.width / inlineSize.height
      : DEFAULT_ASPECT_RATIO;
  const requestedWidth = Math.min(
    inlineSize?.width ?? DEFAULT_FLOATING_WIDTH,
    DEFAULT_FLOATING_WIDTH,
  );
  return constrainFloatingSize(requestedWidth, aspectRatio);
};

export const constrainFloatingSize = (
  width: number,
  aspectRatio: number,
): Size => {
  const maxWidth = Math.max(
    1,
    Math.min(MAX_FLOATING_WIDTH, window.innerWidth - FLOATING_MARGIN * 2),
  );
  const maxHeight = Math.max(1, window.innerHeight - FLOATING_MARGIN * 2);
  const minimumWidth = Math.min(MIN_FLOATING_WIDTH, maxWidth);
  const widthLimitedByHeight = maxHeight * aspectRatio;
  const constrainedWidth = Math.min(
    Math.max(width, minimumWidth),
    maxWidth,
    widthLimitedByHeight,
  );
  return {
    width: constrainedWidth,
    height: constrainedWidth / aspectRatio,
  };
};

export const constrainFloatingPosition = (
  position: Position,
  size: Size,
): Position => ({
  x: Math.min(
    Math.max(position.x, FLOATING_MARGIN),
    Math.max(FLOATING_MARGIN, window.innerWidth - size.width - FLOATING_MARGIN),
  ),
  y: Math.min(
    Math.max(position.y, FLOATING_MARGIN),
    Math.max(
      FLOATING_MARGIN,
      window.innerHeight - size.height - FLOATING_MARGIN,
    ),
  ),
});

export const getCornerPosition = (
  corner: FloatingCorner,
  size: Size,
): StyledPosition => ({
  x: corner.includes("left")
    ? FLOATING_MARGIN
    : `calc(100vw - ${size.width + FLOATING_MARGIN}px)`,
  y: corner.includes("top")
    ? FLOATING_MARGIN
    : `calc(100vh - ${size.height + FLOATING_MARGIN}px)`,
});

export const getSnapCorner = (
  position: Position,
  size: Size,
  velocity: Position,
): FloatingCorner => {
  const centerX = position.x + size.width / 2;
  const centerY = position.y + size.height / 2;
  const projectedX =
    centerX +
    (Math.abs(velocity.x) >= FLICK_VELOCITY_THRESHOLD
      ? velocity.x * FLICK_PROJECTION_MS
      : 0);
  const projectedY =
    centerY +
    (Math.abs(velocity.y) >= FLICK_VELOCITY_THRESHOLD
      ? velocity.y * FLICK_PROJECTION_MS
      : 0);
  const horizontal = projectedX < window.innerWidth / 2 ? "left" : "right";
  const vertical = projectedY < window.innerHeight / 2 ? "top" : "bottom";
  return `${vertical}-${horizontal}`;
};

export const getOppositeCorner = (corner: FloatingCorner): ResizeCorner => {
  const vertical = corner.includes("top") ? "bottom" : "top";
  const horizontal = corner.includes("left") ? "right" : "left";
  return `${vertical}-${horizontal}`;
};

export const getResizeCornerClassName = (corner: ResizeCorner): string => {
  switch (corner) {
    case "top-left":
      return "top-0 left-0 cursor-nwse-resize";
    case "top-right":
      return "top-0 right-0 cursor-nesw-resize";
    case "bottom-left":
      return "bottom-0 left-0 cursor-nesw-resize";
    case "bottom-right":
      return "bottom-0 right-0 cursor-nwse-resize";
  }
};

export const trackPointerGesture = <T extends HTMLElement>(
  event: ReactPointerEvent<T>,
  callbacks: PointerGestureCallbacks,
): (() => void) => {
  const target = event.currentTarget;
  const pointerId = event.pointerId;
  const startClientX = event.clientX;
  const startClientY = event.clientY;
  let active = true;
  let didMove = false;

  const releasePointerCapture = () => {
    try {
      if (target.hasPointerCapture?.(pointerId)) {
        target.releasePointerCapture(pointerId);
      }
    } catch {
      // The browser may release capture before a pointer cancellation reaches us.
    }
  };

  const cleanup = () => {
    window.removeEventListener(
      "pointermove",
      handlePointerMove,
      CAPTURE_EVENT_OPTIONS,
    );
    window.removeEventListener(
      "pointerup",
      handlePointerUp,
      CAPTURE_EVENT_OPTIONS,
    );
    window.removeEventListener(
      "pointercancel",
      handlePointerCancel,
      CAPTURE_EVENT_OPTIONS,
    );
    window.removeEventListener("blur", cancel);
    releasePointerCapture();
  };

  const cancel = () => {
    if (!active) {
      return;
    }
    active = false;
    cleanup();
    callbacks.onCancel();
  };

  function handlePointerMove(moveEvent: PointerEvent) {
    if (!active || moveEvent.pointerId !== pointerId) {
      return;
    }
    if (moveEvent.pointerType === "mouse" && moveEvent.buttons === 0) {
      cancel();
      return;
    }

    if (!didMove) {
      didMove =
        Math.hypot(
          moveEvent.clientX - startClientX,
          moveEvent.clientY - startClientY,
        ) >= MOVE_THRESHOLD;
      if (!didMove) {
        return;
      }
      callbacks.onStart();
    }

    moveEvent.preventDefault();
    callbacks.onMove(moveEvent);
  }

  function handlePointerUp(upEvent: PointerEvent) {
    if (!active || upEvent.pointerId !== pointerId) {
      return;
    }
    active = false;
    cleanup();
    callbacks.onFinish(upEvent, didMove);
  }

  function handlePointerCancel(cancelEvent: PointerEvent) {
    if (cancelEvent.pointerId === pointerId) {
      cancel();
    }
  }

  window.addEventListener(
    "pointermove",
    handlePointerMove,
    CAPTURE_EVENT_OPTIONS,
  );
  window.addEventListener("pointerup", handlePointerUp, CAPTURE_EVENT_OPTIONS);
  window.addEventListener(
    "pointercancel",
    handlePointerCancel,
    CAPTURE_EVENT_OPTIONS,
  );
  window.addEventListener("blur", cancel);
  try {
    target.setPointerCapture?.(pointerId);
  } catch {
    // Pointer capture is an enhancement; window listeners still track the drag.
  }

  return cancel;
};

export const stylePortalContainer = (
  portalContainer: HTMLDivElement,
  options: {
    isFloating: boolean;
    hasExplicitWidth: boolean;
    rounded: boolean;
    size: Size;
    position: StyledPosition | null;
    isInteracting: boolean;
  },
) => {
  const {
    isFloating,
    hasExplicitWidth,
    rounded,
    size,
    position,
    isInteracting,
  } = options;
  portalContainer.dataset.floating = String(isFloating);
  portalContainer.style.position = isFloating ? "fixed" : "relative";
  portalContainer.style.display = "block";
  portalContainer.style.width = isFloating
    ? `${size.width}px`
    : hasExplicitWidth
      ? "100%"
      : "fit-content";
  portalContainer.style.height = isFloating ? `${size.height}px` : "auto";
  portalContainer.style.maxWidth = isFloating
    ? `calc(100vw - ${FLOATING_MARGIN * 2}px)`
    : "100%";
  portalContainer.style.maxHeight = isFloating
    ? `calc(100vh - ${FLOATING_MARGIN * 2}px)`
    : "";
  portalContainer.style.left = position ? toCssPosition(position.x) : "";
  portalContainer.style.top = position ? toCssPosition(position.y) : "";
  portalContainer.style.zIndex = isFloating ? "40" : "";
  portalContainer.style.overflow = isFloating ? "hidden" : "visible";
  portalContainer.style.borderRadius = isFloating
    ? rounded
      ? "4px"
      : "0"
    : "";
  portalContainer.style.background = isFloating ? "black" : "";
  portalContainer.style.boxShadow = isFloating
    ? "0 12px 36px rgb(0 0 0 / 0.35)"
    : "";
  portalContainer.style.cursor = isFloating
    ? isInteracting
      ? "grabbing"
      : "grab"
    : "";
  portalContainer.style.userSelect = isFloating ? "none" : "";
  portalContainer.style.touchAction = isFloating ? "none" : "";
  portalContainer.style.lineHeight = "0";
  portalContainer.style.transition =
    isFloating && !isInteracting && !prefersReducedMotion()
      ? "left 180ms ease-out, top 180ms ease-out"
      : "none";
};

export const animatePortalMove = (
  portalContainer: HTMLDivElement,
  fromRect: DOMRect,
): Animation => {
  const toRect = portalContainer.getBoundingClientRect();
  const scaleX = fromRect.width / Math.max(toRect.width, 1);
  const scaleY = fromRect.height / Math.max(toRect.height, 1);
  return portalContainer.animate(
    [
      {
        transform: `translate3d(${fromRect.left - toRect.left}px, ${fromRect.top - toRect.top}px, 0) scale(${scaleX}, ${scaleY})`,
        transformOrigin: "top left",
        opacity: 0.88,
      },
      {
        transform: "none",
        transformOrigin: "top left",
        opacity: 1,
      },
    ],
    {
      duration: 220,
      easing: "cubic-bezier(0.22, 1, 0.36, 1)",
    },
  );
};

export const prefersReducedMotion = (): boolean =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

export const getFloatingRoot = (
  fullScreenElement: Element | null,
  portalContainer: HTMLDivElement,
): Element => {
  // A parent fullscreen element needs to contain fixed descendants. If the
  // video itself is fullscreen, moving its ancestor there would be invalid.
  if (fullScreenElement && !portalContainer.contains(fullScreenElement)) {
    return fullScreenElement;
  }
  return document.body;
};

const toCssPosition = (value: number | string): string =>
  typeof value === "number" ? `${value}px` : value;
