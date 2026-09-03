/* Copyright 2026 Marimo. All rights reserved. */

import {
  type JSX,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { z } from "zod";
import { useFullScreenElement } from "@/components/ui/fullscreen";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import {
  type FloatingVideoData,
  FloatingVideoPanel,
  FloatingVideoPlaceholder,
  type Size,
} from "./video/floating-video";

export interface VideoData extends FloatingVideoData {
  floating: "manual" | "auto";
}

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

type FloatingReason = "manual" | "auto";

export const VideoComponent = ({
  data,
  host,
}: {
  data: VideoData;
  host: HTMLElement;
}): JSX.Element => {
  const inlineAnchorRef = useRef<HTMLDivElement>(null);
  const portalContainer = useMemo(() => {
    const element = document.createElement("div");
    element.dataset.testid = "marimo-video-container";
    return element;
  }, []);
  const [floatingReason, setFloatingReason] = useState<FloatingReason | null>(
    null,
  );
  const [inlineSize, setInlineSize] = useState<Size | null>(null);
  const wasVisibleRef = useRef(false);
  const dismissedAutoFloatRef = useRef(false);
  const transitionFromRectRef = useRef<DOMRect | null>(null);
  const fullScreenElement = useFullScreenElement();
  const isFloating = floatingReason !== null;

  useLayoutEffect(() => {
    inlineAnchorRef.current?.append(portalContainer);
  }, [portalContainer]);

  const captureInlineSize = useCallback(() => {
    const rect = portalContainer.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      setInlineSize({ width: rect.width, height: rect.height });
    }
  }, [portalContainer]);

  const captureTransitionOrigin = useCallback(() => {
    const rect = portalContainer.getBoundingClientRect();
    if (rect.width > 0 && rect.height > 0) {
      transitionFromRectRef.current = rect;
    }
  }, [portalContainer]);

  const floatVideo = useCallback(() => {
    captureInlineSize();
    captureTransitionOrigin();
    setFloatingReason("manual");
  }, [captureInlineSize, captureTransitionOrigin]);

  const dockVideo = useCallback(() => {
    captureTransitionOrigin();
    if (data.floating === "auto") {
      // Re-arm auto-floating only after the reader sees this location again.
      dismissedAutoFloatRef.current = !isElementInViewport(
        inlineAnchorRef.current,
      );
    }
    setFloatingReason(null);
  }, [captureTransitionOrigin, data.floating]);

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

  useEffect(() => {
    const anchor = inlineAnchorRef.current;
    if (data.floating !== "auto" || !anchor) {
      wasVisibleRef.current = false;
      dismissedAutoFloatRef.current = false;
      if (floatingReason === "auto") {
        captureTransitionOrigin();
        setFloatingReason(null);
      }
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          wasVisibleRef.current = true;
          dismissedAutoFloatRef.current = false;
          if (floatingReason === "auto") {
            captureTransitionOrigin();
            setFloatingReason(null);
          }
        } else if (
          wasVisibleRef.current &&
          !dismissedAutoFloatRef.current &&
          floatingReason === null
        ) {
          captureInlineSize();
          captureTransitionOrigin();
          setFloatingReason("auto");
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(anchor);
    return () => observer.disconnect();
  }, [
    captureInlineSize,
    captureTransitionOrigin,
    data.floating,
    floatingReason,
  ]);

  return (
    <div
      ref={inlineAnchorRef}
      data-testid="marimo-video-anchor"
      className="relative inline-block"
      style={{
        maxWidth: "100%",
        verticalAlign: "top",
        width: data.width ? "100%" : undefined,
        ...(isFloating && inlineSize
          ? { width: inlineSize.width, height: inlineSize.height }
          : null),
      }}
    >
      {isFloating ? (
        <FloatingVideoPlaceholder onDock={dockVideo} rounded={data.rounded} />
      ) : null}
      <FloatingVideoPanel
        data={data}
        fullScreenElement={fullScreenElement}
        hasExplicitWidth={data.width !== undefined}
        inlineAnchorRef={inlineAnchorRef}
        inlineSize={inlineSize}
        isFloating={isFloating}
        onDock={dockVideo}
        onFloat={floatVideo}
        portalContainer={portalContainer}
        transitionFromRectRef={transitionFromRectRef}
      />
    </div>
  );
};

const isElementInViewport = (element: HTMLElement | null): boolean => {
  if (!element) {
    return false;
  }
  const rect = element.getBoundingClientRect();
  return rect.bottom > 0 && rect.top < window.innerHeight;
};
