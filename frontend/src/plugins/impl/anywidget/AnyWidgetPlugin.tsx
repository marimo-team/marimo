/* Copyright 2026 Marimo. All rights reserved. */

import { useAtomValue } from "jotai";
import { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { islandsHydratedAtom } from "@/core/islands/state";
import { createPlugin } from "@/plugins/core/builder";
import type { IPluginProps } from "@/plugins/types";
import { ErrorBanner } from "../common/error-banner";
import { WIDGET_REGISTRY } from "./registry";
import { isWidgetModelId, type WidgetModelId } from "./types";

/**
 * The component's only data attribute; everything else arrives through
 * the model's comm messages, keyed by this id.
 */
interface Data {
  modelId: WidgetModelId;
  esmUrl?: string;
  esmHash?: string;
}

/**
 * Value payload sent by the frontend on state updates.
 *
 * The initial value from the backend is empty — `model_id` is passed
 * via immutable data attributes (`args`) so it survives value overwrites.
 */
interface ModelIdRef {
  model_id?: WidgetModelId;
}

export const AnyWidgetPlugin = createPlugin<ModelIdRef>("marimo-anywidget")
  .withData(
    z.object({
      modelId: z.custom<WidgetModelId>(isWidgetModelId, {
        message: "Expected a non-empty widget model id",
      }),
      esmUrl: z.string().optional(),
      esmHash: z.string().optional(),
    }),
  )
  .withFunctions({})
  .renderer((props) => <AnyWidgetSlot {...props} />);

/**
 * React adapter for a runtime-owned view. React supplies only the render
 * target and its lifetime; the runtime owns models, generations, CSS,
 * composition, and hot reload.
 */
const AnyWidgetSlot = (props: IPluginProps<ModelIdRef, Data>) => {
  const { modelId, esmUrl, esmHash } = props.data;
  const htmlRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<Error>();
  const canCreateView = useAtomValue(islandsHydratedAtom);

  useEffect(() => {
    if (!canCreateView) {
      return;
    }
    const el = htmlRef.current;
    if (!el) {
      return;
    }
    const controller = new AbortController();
    setError(undefined);
    WIDGET_REGISTRY.createView({
      modelId,
      el,
      signal: controller.signal,
      viewSpec: esmUrl && esmHash ? { url: esmUrl, hash: esmHash } : undefined,
    }).catch((error) => {
      if (!controller.signal.aborted) {
        setError(error instanceof Error ? error : new Error(String(error)));
      }
    });
    return () => controller.abort();
  }, [canCreateView, esmHash, esmUrl, modelId]);

  return (
    <>
      {error ? <ErrorBanner error={error} /> : null}
      <div ref={htmlRef} />
    </>
  );
};

export const visibleForTesting = {
  AnyWidgetSlot,
};
