/* Copyright 2024 Marimo. All rights reserved. */

import React, { type PropsWithChildren, useEffect } from "react";
import { Swiper, SwiperSlide, type SwiperRef } from "swiper/react";
import {
  Virtual,
  Keyboard,
  Pagination,
  Zoom,
  Navigation,
} from "swiper/modules";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/cn";
import { useEventListener } from "@/hooks/useEventListener";

import "./slides.css";
import "swiper/css";
import "swiper/css/virtual";
import "swiper/css/keyboard";
import "swiper/css/navigation";
import "swiper/css/pagination";
import "swiper/css/scrollbar";

interface SlidesComponentProps {
  className?: string;
  forceKeyboardNavigation?: boolean;
  index?: string | null;
  height?: string | number | null;
}

const SlidesComponent = ({
  className,
  children,
  height,
  forceKeyboardNavigation = false,
}: PropsWithChildren<SlidesComponentProps>): JSX.Element => {
  const el = React.useRef<SwiperRef>(null);
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  useEventListener(document, "fullscreenchange", () => {
    if (document.fullscreenElement) {
      el.current?.swiper.keyboard.enable();
    } else {
      el.current?.swiper.keyboard.disable();
    }
    setIsFullscreen(!!document.fullscreenElement);
  });

  useEffect(() => {
    requestAnimationFrame(() => {
      window.dispatchEvent(new Event("resize"));
    });
  }, [isFullscreen]);

  return (
    <Swiper
      ref={el}
      className={cn(
        "relative w-full border rounded bg-background mo-slides-theme prose-slides",
        className,
      )}
      spaceBetween={50}
      style={{
        height: isFullscreen ? "100%" : height || "550px",
      }}
      slidesPerView={1}
      modules={[Virtual, Keyboard, Pagination, Zoom, Navigation]}
      zoom={{
        maxRatio: 5,
      }}
      // touch controls interfere with UI elements
      simulateTouch={false}
      keyboard={{
        // Only enable keyboard controls when in fullscreen
        enabled: isFullscreen || forceKeyboardNavigation,
      }}
      navigation={true}
      pagination={{
        clickable: true,
      }}
      virtual={true}
      // Instant swipes, which make sequences of slides
      // that overlay content more legible
      speed={1}
    >
      {React.Children.map(children, (child, index) => {
        if (child == null) {
          return null;
        }
        return (
          <SwiperSlide key={index}>
            <div
              onKeyDown={(e) => {
                // If the target is from a marimo element, stop propagation
                if (
                  e.target instanceof HTMLElement &&
                  e.target.tagName.toLocaleLowerCase().startsWith("marimo-")
                ) {
                  e.stopPropagation();
                }
              }}
              className={cn(
                "h-full w-full flex box-border overflow-y-auto overflow-x-hidden",
                isFullscreen ? "p-20" : "p-6",
              )}
            >
              {/* this centers the contents */}
              <div className="m-auto max-w-full">{child}</div>
            </div>
          </SwiperSlide>
        );
      })}
      <Button
        variant="link"
        size="sm"
        data-testid="marimo-plugin-slides-fullscreen"
        onClick={async () => {
          if (!el.current) {
            return;
          }
          const domEl = el.current as unknown as HTMLElement;

          if (document.fullscreenElement) {
            await document.exitFullscreen();
            setIsFullscreen(false);
          } else {
            await domEl.requestFullscreen();
            setIsFullscreen(true);
          }
        }}
        className="absolute bottom-0 right-0 z-10 mx-1 mb-0"
      >
        {isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
      </Button>
    </Swiper>
  );
};

export default SlidesComponent;
