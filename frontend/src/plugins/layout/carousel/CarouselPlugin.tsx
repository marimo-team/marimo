/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../../stateless-plugin";

import swiperCss from "swiper/css?inline";
import swiperCssVirtual from "swiper/css/virtual?inline";
import swiperCssKeyboard from "swiper/css/keyboard?inline";
import swiperCssNavigation from "swiper/css/navigation?inline";
import swiperCssPagination from "swiper/css/pagination?inline";
import swiperCssScrollbar from "swiper/css/scrollbar?inline";
import React, { type JSX } from "react";

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
    swiperCssKeyboard,
    swiperCssNavigation,
    swiperCssPagination,
    swiperCssScrollbar,
  ];

  render(props: IStatelessPluginProps<Data>): JSX.Element {
    return (
      <LazySlidesComponent {...props.data}>
        {props.children}
      </LazySlidesComponent>
    );
  }
}

const LazySlidesComponent = React.lazy(
  () => import("../../../components/slides/slides-component"),
);
