/* Copyright 2026 Marimo. All rights reserved. */

import React, { type JSX } from "react";
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
  // slidesCss includes swiper css, so we don't need to include it here.
  cssStyles = [slidesCss];

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
