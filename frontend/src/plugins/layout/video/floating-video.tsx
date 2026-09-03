/* Copyright 2026 Marimo. All rights reserved. */

import { Minimize2Icon, PictureInPicture2Icon } from "lucide-react";
import {
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
  type RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { Button } from "@/components/ui/button";
import { createVideoPlaybackKey } from "../../core/video";
import {
  animatePortalMove,
  constrainFloatingPosition,
  constrainFloatingSize,
  type FloatingCorner,
  getCornerPosition,
  getFloatingRoot,
  getInitialFloatingSize,
  getOppositeCorner,
  getResizeCornerClassName,
  getSnapCorner,
  NATIVE_CONTROLS_HEIGHT,
  type Position,
  prefersReducedMotion,
  type ResizeCorner,
  RESIZE_HIT_TARGET_SIZE,
  type Size,
  stylePortalContainer,
  trackPointerGesture,
} from "./floating-video-utils";

export type { Size } from "./floating-video-utils";

export interface FloatingVideoData {
  src?: string | null;
  controls: boolean;
  autoplay: boolean;
  loop: boolean;
  muted: boolean;
  width?: string;
  height?: string;
  rounded: boolean;
}

interface DragGesture {
  offsetX: number;
  offsetY: number;
  lastClientX: number;
  lastClientY: number;
  lastTimestamp: number;
  velocityX: number;
  velocityY: number;
}

interface ResizeGesture {
  startClientX: number;
  startClientY: number;
  startSize: Size;
  aspectRatio: number;
  corner: ResizeCorner;
}

interface FloatingVideoPanelProps {
  data: FloatingVideoData;
  fullScreenElement: Element | null;
  hasExplicitWidth: boolean;
  inlineAnchorRef: RefObject<HTMLDivElement | null>;
  inlineSize: Size | null;
  isFloating: boolean;
  onDock: () => void;
  onFloat: () => void;
  portalContainer: HTMLDivElement;
  transitionFromRectRef: RefObject<DOMRect | null>;
}

interface FloatingVideoPlaceholderProps {
  onDock: () => void;
  rounded: boolean;
}

export const FloatingVideoPanel = ({
  data,
  fullScreenElement,
  hasExplicitWidth,
  inlineAnchorRef,
  inlineSize,
  isFloating,
  onDock,
  onFloat,
  portalContainer,
  transitionFromRectRef,
}: FloatingVideoPanelProps) => {
  const [floatingSize, setFloatingSize] = useState<Size | null>(null);
  const [floatingCorner, setFloatingCorner] =
    useState<FloatingCorner>("bottom-right");
  const [dragPosition, setDragPosition] = useState<Position | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const portalAnimationRef = useRef<Animation | null>(null);
  const activeGestureRef = useRef<(() => void) | null>(null);
  const suppressClickRef = useRef(false);
  const suppressClickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(
    null,
  );

  const resolvedFloatingSize = useMemo(
    () => floatingSize ?? getInitialFloatingSize(inlineSize),
    [floatingSize, inlineSize],
  );

  const cancelAnimation = useCallback(() => {
    portalAnimationRef.current?.cancel();
    portalAnimationRef.current = null;
    transitionFromRectRef.current = null;
  }, [transitionFromRectRef]);

  const cancelActiveGesture = useCallback(() => {
    activeGestureRef.current?.();
    activeGestureRef.current = null;
  }, []);

  const suppressNextClick = useCallback(() => {
    suppressClickRef.current = true;
    if (suppressClickTimerRef.current !== null) {
      clearTimeout(suppressClickTimerRef.current);
    }
    suppressClickTimerRef.current = setTimeout(() => {
      suppressClickRef.current = false;
      suppressClickTimerRef.current = null;
    }, 0);
  }, []);

  const handleClickCapture = useCallback(
    (event: ReactMouseEvent<HTMLDivElement>) => {
      if (!suppressClickRef.current) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      suppressClickRef.current = false;
      if (suppressClickTimerRef.current !== null) {
        clearTimeout(suppressClickTimerRef.current);
        suppressClickTimerRef.current = null;
      }
    },
    [],
  );

  const handleDragPointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!isFloating || event.button !== 0) {
        return;
      }
      if (
        (event.target as HTMLElement).closest(
          "button, [data-floating-video-resize]",
        )
      ) {
        return;
      }

      const rect = portalContainer.getBoundingClientRect();
      // Native video controls live in a closed shadow root, so pointer events are
      // retargeted to the video element. Reserve their strip for seeking and the
      // other native controls instead of turning those gestures into drags.
      const controlsHeight = Math.min(
        NATIVE_CONTROLS_HEIGHT,
        rect.height * 0.3,
      );
      if (data.controls && event.clientY >= rect.bottom - controlsHeight) {
        return;
      }

      cancelActiveGesture();
      const gesture: DragGesture = {
        offsetX: event.clientX - rect.left,
        offsetY: event.clientY - rect.top,
        lastClientX: event.clientX,
        lastClientY: event.clientY,
        lastTimestamp: event.timeStamp,
        velocityX: 0,
        velocityY: 0,
      };

      activeGestureRef.current = trackPointerGesture(event, {
        onStart: () => {
          cancelAnimation();
          setIsDragging(true);
          setIsResizing(false);
        },
        onMove: (moveEvent) => {
          const elapsed = Math.max(
            moveEvent.timeStamp - gesture.lastTimestamp,
            1,
          );
          gesture.velocityX =
            (moveEvent.clientX - gesture.lastClientX) / elapsed;
          gesture.velocityY =
            (moveEvent.clientY - gesture.lastClientY) / elapsed;
          gesture.lastClientX = moveEvent.clientX;
          gesture.lastClientY = moveEvent.clientY;
          gesture.lastTimestamp = moveEvent.timeStamp;

          setDragPosition(
            constrainFloatingPosition(
              {
                x: moveEvent.clientX - gesture.offsetX,
                y: moveEvent.clientY - gesture.offsetY,
              },
              resolvedFloatingSize,
            ),
          );
        },
        onFinish: (finishEvent, didMove) => {
          setIsDragging(false);
          if (!didMove) {
            return;
          }

          const elapsed = Math.max(
            finishEvent.timeStamp - gesture.lastTimestamp,
            1,
          );
          if (elapsed < 100) {
            gesture.velocityX =
              (finishEvent.clientX - gesture.lastClientX) / elapsed;
            gesture.velocityY =
              (finishEvent.clientY - gesture.lastClientY) / elapsed;
          }

          const position = constrainFloatingPosition(
            {
              x: finishEvent.clientX - gesture.offsetX,
              y: finishEvent.clientY - gesture.offsetY,
            },
            resolvedFloatingSize,
          );
          setFloatingCorner(
            getSnapCorner(position, resolvedFloatingSize, {
              x: gesture.velocityX,
              y: gesture.velocityY,
            }),
          );
          setDragPosition(null);
          suppressNextClick();
        },
        onCancel: () => {
          setIsDragging(false);
          setDragPosition(null);
        },
      });
    },
    [
      cancelActiveGesture,
      cancelAnimation,
      data.controls,
      isFloating,
      portalContainer,
      resolvedFloatingSize,
      suppressNextClick,
    ],
  );

  const resizeCorner = getOppositeCorner(floatingCorner);

  const handleResizePointerDown = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      if (!isFloating || event.button !== 0) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      cancelActiveGesture();
      const gesture: ResizeGesture = {
        startClientX: event.clientX,
        startClientY: event.clientY,
        startSize: resolvedFloatingSize,
        aspectRatio: resolvedFloatingSize.width / resolvedFloatingSize.height,
        corner: resizeCorner,
      };

      activeGestureRef.current = trackPointerGesture(event, {
        onStart: () => {
          cancelAnimation();
          setIsResizing(true);
          setIsDragging(false);
        },
        onMove: (moveEvent) => {
          const horizontalDirection = gesture.corner.includes("right") ? 1 : -1;
          const verticalDirection = gesture.corner.includes("bottom") ? 1 : -1;
          const widthDelta =
            (moveEvent.clientX - gesture.startClientX) * horizontalDirection;
          const heightDelta =
            (moveEvent.clientY - gesture.startClientY) * verticalDirection;
          const widthFromHorizontal = gesture.startSize.width + widthDelta;
          const widthFromVertical =
            gesture.startSize.width + heightDelta * gesture.aspectRatio;
          const nextWidth =
            Math.abs(widthDelta) >= Math.abs(heightDelta * gesture.aspectRatio)
              ? widthFromHorizontal
              : widthFromVertical;
          setFloatingSize(
            constrainFloatingSize(nextWidth, gesture.aspectRatio),
          );
        },
        onFinish: () => setIsResizing(false),
        onCancel: () => setIsResizing(false),
      });
    },
    [
      cancelActiveGesture,
      cancelAnimation,
      isFloating,
      resizeCorner,
      resolvedFloatingSize,
    ],
  );

  useEffect(() => {
    if (!isFloating) {
      cancelActiveGesture();
      setIsDragging(false);
      setIsResizing(false);
      setDragPosition(null);
    }
  }, [cancelActiveGesture, isFloating]);

  useEffect(() => {
    if (!isFloating) {
      return;
    }

    const constrainToViewport = () => {
      setFloatingSize((current) => {
        const size = current ?? getInitialFloatingSize(inlineSize);
        const next = constrainFloatingSize(
          size.width,
          size.width / size.height,
        );
        return next.width === size.width && next.height === size.height
          ? current
          : next;
      });
    };

    window.addEventListener("resize", constrainToViewport);
    constrainToViewport();
    return () => window.removeEventListener("resize", constrainToViewport);
  }, [inlineSize, isFloating]);

  useLayoutEffect(() => {
    const parent = isFloating
      ? getFloatingRoot(fullScreenElement, portalContainer)
      : inlineAnchorRef.current;
    if (parent && portalContainer.parentElement !== parent) {
      parent.append(portalContainer);
    }

    stylePortalContainer(portalContainer, {
      isFloating,
      hasExplicitWidth,
      rounded: data.rounded,
      size: resolvedFloatingSize,
      position:
        isFloating && dragPosition
          ? dragPosition
          : isFloating
            ? getCornerPosition(floatingCorner, resolvedFloatingSize)
            : null,
      isInteracting: isDragging || isResizing,
    });

    const fromRect = transitionFromRectRef.current;
    transitionFromRectRef.current = null;
    if (
      fromRect &&
      !prefersReducedMotion() &&
      typeof portalContainer.animate === "function"
    ) {
      portalAnimationRef.current?.cancel();
      const animation = animatePortalMove(portalContainer, fromRect);
      portalAnimationRef.current = animation;
      animation.onfinish = () => {
        if (portalAnimationRef.current === animation) {
          portalAnimationRef.current = null;
        }
      };
      animation.oncancel = () => {
        if (portalAnimationRef.current === animation) {
          portalAnimationRef.current = null;
        }
      };
    }
  }, [
    dragPosition,
    floatingCorner,
    fullScreenElement,
    hasExplicitWidth,
    inlineAnchorRef,
    isDragging,
    isFloating,
    isResizing,
    portalContainer,
    data.rounded,
    resolvedFloatingSize,
    transitionFromRectRef,
  ]);

  useEffect(() => {
    return () => {
      cancelActiveGesture();
      portalAnimationRef.current?.cancel();
      if (suppressClickTimerRef.current !== null) {
        clearTimeout(suppressClickTimerRef.current);
      }
      portalContainer.remove();
    };
  }, [cancelActiveGesture, portalContainer]);

  const portalContent = (
    <div
      data-testid="floating-video-surface"
      className={isFloating ? "relative size-full" : "contents"}
      onClickCapture={handleClickCapture}
      onPointerDown={handleDragPointerDown}
    >
      <video
        key={createVideoPlaybackKey(data)}
        data-testid="marimo-video"
        src={data.src ?? undefined}
        controls={data.controls}
        autoPlay={data.autoplay}
        loop={data.loop}
        muted={data.muted}
        disablePictureInPicture={true}
        className={isFloating ? "block size-full object-contain" : undefined}
        style={{
          width: isFloating ? "100%" : data.width,
          height: isFloating ? "100%" : data.height,
          borderRadius: data.rounded ? "4px" : undefined,
        }}
      />
      <Button
        data-testid="floating-video-toggle"
        variant="secondary"
        size="icon"
        className={`absolute bottom-2 z-10 size-7 opacity-75 shadow-md transition-opacity hover:opacity-100 ${
          isFloating && floatingCorner.includes("right") ? "left-2" : "right-2"
        }`}
        onPointerDown={(event) => event.stopPropagation()}
        onClick={isFloating ? onDock : onFloat}
        aria-label={isFloating ? "Return video inline" : "Float video"}
        title={isFloating ? "Return video inline" : "Float video"}
      >
        {isFloating ? (
          <Minimize2Icon className="size-4" />
        ) : (
          <PictureInPicture2Icon className="size-4" />
        )}
      </Button>
      {isFloating && (
        <div
          data-testid="marimo-video-resize-corner"
          data-floating-video-resize="true"
          aria-hidden="true"
          className={`absolute z-20 touch-none ${getResizeCornerClassName(resizeCorner)}`}
          style={{
            width: RESIZE_HIT_TARGET_SIZE,
            height: RESIZE_HIT_TARGET_SIZE,
          }}
          onPointerDown={handleResizePointerDown}
        />
      )}
    </div>
  );

  return createPortal(portalContent, portalContainer);
};

export const FloatingVideoPlaceholder = ({
  onDock,
  rounded,
}: FloatingVideoPlaceholderProps) => (
  <div
    data-testid="marimo-video-placeholder"
    className="flex h-full w-full min-h-28 flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border bg-muted/40 p-4 text-center text-muted-foreground"
    style={{ borderRadius: rounded ? "4px" : "0" }}
  >
    <PictureInPicture2Icon className="size-7" aria-hidden="true" />
    <span role="status" className="text-sm font-medium">
      Video is playing in a floating window
    </span>
    <Button variant="outline" size="sm" onClick={onDock}>
      Return video here
    </Button>
  </div>
);
