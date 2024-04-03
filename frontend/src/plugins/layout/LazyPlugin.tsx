/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";

import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { useAsyncData } from "@/hooks/useAsyncData";
import { ErrorBanner } from "../impl/common/error-banner";
import { renderHTML } from "../core/RenderHTML";
import { useIntersectionObserver } from "@uidotdev/usehooks";
import { useRef } from "react";
import { Loader2Icon } from "lucide-react";

interface Data {
  showLoadingIndicator: boolean;
}

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  load: (req: {}) => Promise<{
    html: string;
  }>;
};

type S = undefined;

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
  .renderer((props) => <LazyComponent {...props.data} {...props.functions} />);

type Props = PluginFunctions & Data;

const LazyComponent = ({ load, showLoadingIndicator }: Props): JSX.Element => {
  const [ref, entry] = useIntersectionObserver({
    threshold: 0,
    root: null,
    rootMargin: "0px",
  });

  const hasIntersected = useRef<boolean>(false);
  if (entry?.isIntersecting) {
    hasIntersected.current = true;
  }

  const { data, loading, error } = useAsyncData(() => {
    if (!hasIntersected.current) {
      return Promise.resolve({ html: "" });
    }
    return load({});
  }, [hasIntersected.current]);

  if (error) {
    return <ErrorBanner error={error} />;
  }

  return (
    <div ref={ref} className="min-h-4">
      {loading && showLoadingIndicator ? (
        <Loader2Icon className="w-12 h-12 animate-spin text-primary my-4 mx-4" />
      ) : (
        data && renderHTML({ html: data.html })
      )}
    </div>
  );
};
