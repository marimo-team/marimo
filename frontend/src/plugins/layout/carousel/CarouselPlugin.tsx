/* Copyright 2026 Marimo. All rights reserved. */

import React, { type JSX } from "react";
import swiperCssNavigation from "swiper/css/navigation?inline";
import swiperCssPagination from "swiper/css/pagination?inline";
import swiperCssScrollbar from "swiper/css/scrollbar?inline";
import swiperCssVirtual from "swiper/css/virtual?inline";
import swiperCss from "swiper/css?inline";
import { z } from "zod";
import slidesCss from "@/components/slides/slides.css?inline";
import swiperSlidesCss from "@/components/slides/swiper-slides.css?inline";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../../stateless-plugin";

interface Data {
  index?: string | null;
  height?: string | number | null;
}

export class CarouselPlugin implements IStatelessPlugin<Data> {
  public tagName = "marimo-carousel";

  public validator = z.object({
    index: z.string().nullish(),
    height: z.union([z.string(), z.number()]).nullish(),
  });

  // TODO: Move async when we support async css
  public cssStyles = [
    swiperCss,
    swiperCssVirtual,
    swiperCssNavigation,
    swiperCssPagination,
    swiperCssScrollbar,
    slidesCss,
    swiperSlidesCss,
  ];

  public render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <LazySlidesComponent {...props.data} wrapAround={true}>
        {props.children}
      </LazySlidesComponent>
    );
  }
}

const LazySlidesComponent = React.lazy(
  () => import("../../../components/slides/swiper-component"),
);
