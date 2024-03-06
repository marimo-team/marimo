/* Copyright 2024 Marimo. All rights reserved. */
import React, { PropsWithChildren, useEffect } from "react";
import { z } from "zod";
import { IStatelessPlugin, IStatelessPluginProps } from "../stateless-plugin";
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

import "./carousel.css";
import swiperCss from "swiper/css?inline";
import swiperCssVirtual from "swiper/css/virtual?inline";
import swiperCssKeyboard from "swiper/css/keyboard?inline";
import swiperCssNavigation from "swiper/css/navigation?inline";
import swiperCssPagination from "swiper/css/pagination?inline";
import swiperCssScrollbar from "swiper/css/scrollbar?inline";

interface Data {
  index?: string | null;
  height?: string | number | null;
}

export class CarouselPlugin implements IStatelessPlugin<Data> {
  tagName = "marimo-carousel";

  validator = z.object({
    index: z.string().nullish(),
    height: z.union([z.string(), z.number()]).nullish(),
  });

  cssStyles = [
    swiperCss,
    swiperCssVirtual,
    swiperCssKeyboard,
    swiperCssNavigation,
    swiperCssPagination,
    swiperCssScrollbar,
  ];

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <CarouselComponent {...props.data}>{props.children}</CarouselComponent>
    );
  }
}

type CarouselComponentProps = Data;

const CarouselComponent = ({
  children,
  height,
}: PropsWithChildren<CarouselComponentProps>): JSX.Element => {
  const el = React.useRef<SwiperRef>(null);
  const [isFullscreen, setIsFullscreen] = React.useState(false);

  useEventListener(document, "fullscreenchange", () => {
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
        enabled: true,
        onlyInViewport: true,
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
