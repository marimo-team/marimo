/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "../impl/common/error-banner";
import { renderHTML } from "../core/RenderHTML";
import { useIntersectionObserver } from "@uidotdev/usehooks";
import { Loader2Icon } from "lucide-react";

import type { JSX } from "react";

interface Data {
  showLoadingIndicator: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  load: (req: {}) => Promise<{
    html: string;
  }>;
};

// Whether it has been loaded
type S = boolean;

export const LazyPlugin = createPlugin<S>("marimo-lazy")
  .withData(
    z.object({
      showLoadingIndicator: z.boolean().default(false),
    }),
  )
  .withFunctions<PluginFunctions>({
    load: rpc.input(z.object({})).output(
      z.object({
        html: z.string(),
      }),
    ),
  })
  .renderer((props) => (
    <LazyComponent
      value={props.value}
      setValue={props.setValue}
      {...props.data}
      {...props.functions}
    />
  ));

interface Props extends PluginFunctions, Data {
  value: boolean;
  setValue: (value: S) => void;
}

const LazyComponent = ({
  load,
  showLoadingIndicator,
  value,
  setValue,
}: Props): JSX.Element => {
  const [ref, entry] = useIntersectionObserver({
    threshold: 0,
    root: null,
    rootMargin: "0px",
  });

  if (entry?.isIntersecting && !value) {
    setValue(true);
  }

  // For each re-render, we have to make a waterfall request
  // We could improve performance if the BE was able to know if the same
  // mo.lazy has already been loaded, and when re-rendering it would
  // include the 'lazy' content by default (unlazily)
  const { data, loading, error } = useAsyncData(
    (ctx) => {
      if (!value) {
        ctx.previous();
        return Promise.resolve(undefined);
      }
      return load({});
    },
    [value],
  );

  if (error) {
    return <ErrorBanner error={error} />;
  }

  return (
    <div ref={ref} className="min-h-4">
      {loading && !data && showLoadingIndicator ? (
        <Loader2Icon className="w-12 h-12 animate-spin text-primary my-4 mx-4" />
      ) : (
        data && renderHTML({ html: data.html })
      )}
    </div>
  );
};
