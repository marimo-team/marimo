/* Copyright 2024 Marimo. All rights reserved. */

import "./carousel.css";

import React, { PropsWithChildren, useEffect } from "react";
import { Swiper, SwiperSlide, SwiperRef } from "swiper/react";
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

interface CarouselComponentProps {
  index?: string | null;
  height?: string | number | null;
}
const CarouselComponent = ({
  children,
  height,
}: PropsWithChildren<CarouselComponentProps>): JSX.Element => {
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
      className="relative w-full border rounded bg-background mo-carousel"
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
        enabled: isFullscreen,
      }}
      navigation={true}
      pagination={{
        clickable: true,
      }}
      virtual={true}
    >
      {React.Children.map(children, (child, index) => {
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
                "h-full w-full flex items-center justify-center box-border overflow-hidden",
                isFullscreen ? "p-20" : "p-6",
              )}
            >
              {child}
            </div>
          </SwiperSlide>
        );
      })}
      <Button
        variant="link"
        size="sm"
        data-testid="marimo-plugin-carousel-fullscreen"
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

export default CarouselComponent;
