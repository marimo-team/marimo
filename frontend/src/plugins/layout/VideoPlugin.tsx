/* Copyright 2026 Marimo. All rights reserved. */

import { Minimize2Icon, PictureInPicture2Icon } from "lucide-react";
import {
  type CSSProperties,
  type JSX,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { useFullScreenElement } from "@/components/ui/fullscreen";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";

export interface VideoData {
  src?: string | null;
  controls: boolean;
  muted: boolean;
  autoplay: boolean;
  loop: boolean;
  rounded: boolean;
  floating: "manual" | "auto";
  width?: string;
  height?: string;
}

interface InlineSize {
  width: number;
  height: number;
}

type FloatingReason = "manual" | "auto" | null;

const FLOATING_MARGIN = 16;
const MAX_FLOATING_WIDTH = 360;

export class VideoPlugin implements IStatelessPlugin<VideoData> {
  tagName = "marimo-video";

  validator = z.object({
    src: z.string().nullish(),
    controls: z.boolean().default(true),
    muted: z.boolean().default(false),
    autoplay: z.boolean().default(false),
    loop: z.boolean().default(false),
    rounded: z.boolean().default(false),
    floating: z.enum(["manual", "auto"]),
    width: z.string().optional(),
    height: z.string().optional(),
  });

  render(props: IStatelessPluginProps<VideoData>): JSX.Element {
    return <VideoComponent data={props.data} host={props.host} />;
  }
}

export const VideoComponent = ({
  data,
  host,
}: {
  data: VideoData;
  host: HTMLElement;
}): JSX.Element => {
  const inlineAnchorRef = useRef<HTMLDivElement>(null);
  const [portalContainer] = useState(() => {
    const element = document.createElement("div");
    element.dataset.testid = "marimo-video-container";
    return element;
  });
  const [floatingReason, setFloatingReason] = useState<FloatingReason>(null);
  const [inlineSize, setInlineSize] = useState<InlineSize | null>(null);
  const hasBeenVisibleRef = useRef(false);
  const autoFloatingDismissedRef = useRef(false);
  const fullScreenElement = useFullScreenElement();
  const isFloating = floatingReason !== null;

  useLayoutEffect(() => {
    const previousDisplay = host.style.display;
    const previousMaxWidth = host.style.maxWidth;
    const previousWidth = host.style.width;

    host.style.display = "inline-block";
    host.style.maxWidth = "100%";
    host.style.width = data.width ?? "";

    return () => {
      host.style.display = previousDisplay;
      host.style.maxWidth = previousMaxWidth;
      host.style.width = previousWidth;
    };
  }, [data.width, host]);

  const captureInlineSize = useCallback(() => {
    const rect = portalContainer.getBoundingClientRect();
    setInlineSize({ width: rect.width, height: rect.height });
  }, [portalContainer]);

  const floatManually = useCallback(() => {
    captureInlineSize();
    autoFloatingDismissedRef.current = false;
    setFloatingReason("manual");
  }, [captureInlineSize]);

  const dockVideo = useCallback(() => {
    if (data.floating === "auto") {
      // Do not immediately float again while the inline anchor is still out
      // of view. Re-arm auto-floating once the reader sees the anchor again.
      autoFloatingDismissedRef.current = !isElementInViewport(
        inlineAnchorRef.current,
      );
    }
    setFloatingReason(null);
  }, [data.floating]);

  useEffect(() => {
    if (data.floating !== "auto" || !inlineAnchorRef.current) {
      return;
    }

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        hasBeenVisibleRef.current = true;
        autoFloatingDismissedRef.current = false;
        setFloatingReason((reason) => (reason === "auto" ? null : reason));
        return;
      }

      // A video below the fold should not float before the reader reaches it.
      if (hasBeenVisibleRef.current && !autoFloatingDismissedRef.current) {
        captureInlineSize();
        setFloatingReason((reason) => reason ?? "auto");
      }
    });

    observer.observe(inlineAnchorRef.current);
    return () => observer.disconnect();
  }, [captureInlineSize, data.floating]);

  useEffect(() => {
    if (data.floating === "manual") {
      setFloatingReason((reason) => (reason === "auto" ? null : reason));
    }
  }, [data.floating]);

  useLayoutEffect(() => {
    const target = isFloating
      ? getFloatingRoot(fullScreenElement, portalContainer)
      : inlineAnchorRef.current;
    if (!target) {
      return;
    }

    target.append(portalContainer);
    stylePortalContainer(portalContainer, {
      isFloating,
      hasExplicitWidth: data.width !== undefined,
      inlineWidth: inlineSize?.width,
    });
  }, [
    data.width,
    fullScreenElement,
    inlineSize?.width,
    isFloating,
    portalContainer,
  ]);

  useEffect(() => {
    return () => portalContainer.remove();
  }, [portalContainer]);

  const anchorStyle: CSSProperties = {
    display: "inline-block",
    maxWidth: "100%",
    verticalAlign: "top",
    width: data.width ? "100%" : undefined,
    ...(isFloating && inlineSize
      ? {
          width: inlineSize.width,
          height: inlineSize.height,
        }
      : null),
  };

  const actionLabel = isFloating ? "Return video inline" : "Float video";

  return (
    <>
      <div
        ref={inlineAnchorRef}
        data-testid="marimo-video-anchor"
        style={anchorStyle}
      />
      {createPortal(
        <>
          <video
            key={`${data.src}-${data.autoplay}-${data.muted}-${data.loop}`}
            data-testid="marimo-video"
            src={data.src ?? undefined}
            controls={data.controls}
            muted={data.muted}
            autoPlay={data.autoplay}
            loop={data.loop}
            playsInline={true}
            disablePictureInPicture={true}
            style={{
              display: "block",
              width: isFloating ? "100%" : data.width ? "100%" : undefined,
              height: isFloating ? "auto" : data.height,
              maxWidth: "100%",
              maxHeight: isFloating
                ? `calc(100vh - ${FLOATING_MARGIN * 2}px)`
                : undefined,
              borderRadius: data.rounded ? 4 : undefined,
              objectFit: "contain",
            }}
          />
          <Button
            type="button"
            variant="secondary"
            size="icon"
            aria-label={actionLabel}
            title={actionLabel}
            aria-pressed={isFloating}
            onClick={isFloating ? dockVideo : floatManually}
            className="absolute top-2 right-2 z-10 h-8 w-8 mb-0 border-white/30 bg-black/70 text-white opacity-80 hover:opacity-100 hover:bg-black/85 focus-visible:opacity-100"
          >
            {isFloating ? (
              <Minimize2Icon className="h-4 w-4" />
            ) : (
              <PictureInPicture2Icon className="h-4 w-4" />
            )}
          </Button>
        </>,
        portalContainer,
      )}
    </>
  );
};

function stylePortalContainer(
  container: HTMLDivElement,
  {
    isFloating,
    hasExplicitWidth,
    inlineWidth,
  }: {
    isFloating: boolean;
    hasExplicitWidth: boolean;
    inlineWidth?: number;
  },
): void {
  const floatingWidth = Math.min(
    inlineWidth && inlineWidth > 0 ? inlineWidth : MAX_FLOATING_WIDTH,
    MAX_FLOATING_WIDTH,
  );

  Object.assign(container.style, {
    position: isFloating ? "fixed" : "relative",
    right: isFloating ? `${FLOATING_MARGIN}px` : "",
    bottom: isFloating ? `${FLOATING_MARGIN}px` : "",
    zIndex: isFloating ? "40" : "",
    display: "block",
    width: isFloating
      ? `${floatingWidth}px`
      : hasExplicitWidth
        ? "100%"
        : "fit-content",
    maxWidth: isFloating ? `calc(100vw - ${FLOATING_MARGIN * 2}px)` : "100%",
    overflow: isFloating ? "hidden" : "visible",
    borderRadius: isFloating ? "8px" : "",
    background: isFloating ? "black" : "transparent",
    boxShadow: isFloating
      ? "0 16px 48px rgb(0 0 0 / 35%), 0 2px 8px rgb(0 0 0 / 25%)"
      : "none",
    lineHeight: "0",
  });
}

function isElementInViewport(element: HTMLElement | null): boolean {
  if (!element) {
    return false;
  }
  const rect = element.getBoundingClientRect();
  return rect.bottom > 0 && rect.top < window.innerHeight;
}

function getFloatingRoot(
  fullScreenElement: Element | null,
  portalContainer: HTMLElement,
): Element {
  // If the video itself enters fullscreen, it is already visible above the
  // page. Appending its ancestor to it would create an invalid DOM hierarchy.
  if (fullScreenElement && !portalContainer.contains(fullScreenElement)) {
    return fullScreenElement;
  }
  return document.body;
}
