/* Copyright 2024 Marimo. All rights reserved. */
import React from "react";
import { z } from "zod";
import type {
  IStatelessPlugin,
  IStatelessPluginProps,
} from "../stateless-plugin";
import type { ImageComparisonData } from "../impl/image-comparison/ImageComparisonComponent";

const LazyImageComparisonComponent = React.lazy(
  () => import("../impl/image-comparison/ImageComparisonComponent"),
);

export class ImageComparisonPlugin
  implements IStatelessPlugin<ImageComparisonData>
{
  tagName = "marimo-image-comparison";

  validator = z.object({
    beforeSrc: z.string(),
    afterSrc: z.string(),
    value: z.number().min(0).max(100).default(50),
    direction: z.enum(["horizontal", "vertical"]).default("horizontal"),
    showLabels: z.boolean().default(false),
    beforeLabel: z.string().default("Before"),
    afterLabel: z.string().default("After"),
    width: z.string().optional(),
    height: z.string().optional(),
  });

  render(props: IStatelessPluginProps<ImageComparisonData>): JSX.Element {
    return (
      <React.Suspense fallback={<div>Loading image comparison...</div>}>
        <LazyImageComparisonComponent {...props.data} />
      </React.Suspense>
    );
  }
}
