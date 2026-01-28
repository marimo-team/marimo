/* Copyright 2026 Marimo. All rights reserved. */

import React, { type JSX } from "react";
import swiperCssNavigation from "swiper/css/navigation?inline";
import swiperCssPagination from "swiper/css/pagination?inline";
import swiperCssScrollbar from "swiper/css/scrollbar?inline";
import swiperCssVirtual from "swiper/css/virtual?inline";
import swiperCss from "swiper/css?inline";
import { z } from "zod";
import slidesCss from "@/components/slides/slides.css?inline";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../../stateless-plugin";

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

  // TODO: Move async when we support async css
  cssStyles = [
    swiperCss,
    swiperCssVirtual,
    swiperCssNavigation,
    swiperCssPagination,
    swiperCssScrollbar,
    slidesCss,
  ];

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <LazySlidesComponent {...props.data} wrapAround={true}>
        {props.children}
      </LazySlidesComponent>
    );
  }
}

const LazySlidesComponent = React.lazy(
  () => import("../../../components/slides/slides-component"),
);
