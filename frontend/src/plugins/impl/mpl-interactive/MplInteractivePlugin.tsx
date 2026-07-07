/* Copyright 2026 Marimo. All rights reserved. */
/* oxlint-disable typescript/no-explicit-any */

import { useCallback, useEffect, useRef } from "react";
import { z } from "zod";
import { useEventListener } from "@/hooks/useEventListener";
import { createPlugin } from "@/plugins/core/builder";
import { isTrustedVirtualFileUrl } from "@/plugins/core/trusted-url";
import { MODEL_MANAGER, type Model } from "@/plugins/impl/anywidget/model";
import type { ModelState, WidgetModelId } from "@/plugins/impl/anywidget/types";
import type { IPluginProps } from "@/plugins/types";
import { downloadBlob } from "@/utils/download";
import { Logger } from "@/utils/Logger";
import { MplCommWebSocket } from "./mpl-websocket-shim";
import { Functions } from "@/utils/functions";

const MPL_SCOPE_CLASS = "mpl-interactive-figure";

interface Data {
  mplJsUrl: string;
  cssUrl: string;
  toolbarImages: Record<string, string>;
  width: number;
  height: number;
}

interface ModelIdRef {
  model_id: WidgetModelId;
}

declare global {
  interface Window {
    mpl: {
      figure: new (
        id: string,
        ws: MplCommWebSocket,
        ondownload: (figure: MplFigure, format: string) => void,
        element: HTMLElement,
      ) => MplFigure;
      toolbar_items: [
        string | null,
        string | null,
        string | null,
        string | null,
      ][];
    };
  }
}

interface MplFigure {
  id: string;
  ws: MplCommWebSocket;
  root: HTMLElement;
  send_message: (type: string, properties: Record<string, unknown>) => void;
}

export const MplInteractivePlugin = createPlugin<ModelIdRef>(
  "marimo-mpl-interactive",
)
  .withData(
    z.object({
      mplJsUrl: z.string(),
      cssUrl: z.string(),
      toolbarImages: z.record(z.string(), z.string()),
      width: z.number(),
      height: z.number(),
    }),
  )
  .withFunctions({})
  .renderer((props) => <MplInteractiveSlot {...props} />);

let mplJsLoading: Promise<void> | null = null;

async function ensureMplJs(jsUrl: string): Promise<void> {
  if (window.mpl) {
    return;
  }
  if (!isTrustedVirtualFileUrl(jsUrl)) {
    throw new Error(
      `Refusing to load mpl.js from untrusted URL: ${String(jsUrl)}`,
    );
  }
  if (mplJsLoading) {
    return mplJsLoading;
  }
  mplJsLoading = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = jsUrl;
    script.onload = () => resolve();
    script.onerror = () => {
      mplJsLoading = null;
      reject(new Error("Failed to load mpl.js"));
    };
    document.head.append(script);
  });
  return mplJsLoading;
}

/**
 * Patch mpl.js toolbar image references to use inline data URIs.
 *
 * mpl.js sets `icon_img.src = '_images/' + image + '.png'` and
 * `icon_img.srcset = '_images/' + image + '_large.png 2x'`.
 *
 * We observe the container for new <img> elements and rewrite their
 * src/srcset to the inlined base64 data URIs.
 */
function patchToolbarImages(
  container: HTMLElement,
  toolbarImages: Record<string, string>,
): () => void {
  const patchImg = (img: HTMLImageElement) => {
    const src = img.getAttribute("src") || "";
    const match = src.match(/_images\/(.+)\.png$/);
    if (match) {
      const name = match[1];
      const dataUri = toolbarImages[name];
      if (dataUri) {
        img.src = dataUri;
      }
    }
    const srcset = img.getAttribute("srcset") || "";
    const srcsetMatch = srcset.match(/_images\/(.+)\.png\s+2x$/);
    if (srcsetMatch) {
      const name = srcsetMatch[1];
      const dataUri = toolbarImages[name];
      if (dataUri) {
        img.srcset = `${dataUri} 2x`;
      }
    }
  };

  // Patch any existing images
  for (const img of container.querySelectorAll("img")) {
    patchImg(img);
  }

  // Observe for new images added by mpl.js
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node instanceof HTMLImageElement) {
          patchImg(node);
        } else if (node instanceof HTMLElement) {
          for (const img of node.querySelectorAll("img")) {
            patchImg(img);
          }
        }
      }
    }
  });

  observer.observe(container, { childList: true, subtree: true });
  return () => observer.disconnect();
}

function injectCss(container: HTMLElement, cssUrl: string): () => void {
  if (!isTrustedVirtualFileUrl(cssUrl)) {
    Logger.error(
      `Refusing to load mpl CSS from untrusted URL: ${String(cssUrl)}`,
    );
    return Functions.NOOP;
  }
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = cssUrl;
  container.append(link);
  return () => link.remove();
}

const MplInteractiveSlot = (props: IPluginProps<ModelIdRef, Data>) => {
  const { mplJsUrl, cssUrl, toolbarImages, width, height } = props.data;
  const { model_id: modelId } = props.value;
  const containerRef = useRef<HTMLDivElement>(null);
  const figureRef = useRef<MplFigure | null>(null);
  const wsRef = useRef<MplCommWebSocket | null>(null);
  // Sends to the currently bound backend model. Re-pointed on every (re)bind
  // so the persistent socket and toolbar downloads always reach the live comm.
  const sendRef = useRef<(msg: unknown) => void>(Functions.NOOP);
  // Detaches the model bound by the most recent bindModel call. Shared between
  // the mount and rebind effects so a rerun disposes the prior model's
  // listener before attaching the next one (never stacking listeners).
  const boundModelCleanupRef = useRef<(() => void) | undefined>(undefined);
  // Latest model id, read by the mount effect without being a dependency:
  // the figure is built once, and switching to a new model is the rebind
  // effect's job, not a reason to tear the canvas down.
  const modelIdRef = useRef(modelId);
  modelIdRef.current = modelId;
  // The data attributes are re-parsed into fresh objects on every rerun, so
  // `toolbarImages` changes identity even when its contents do not. Read it
  // from a ref so it can't retrigger the mount effect and rebuild the canvas.
  const toolbarImagesRef = useRef(toolbarImages);
  toolbarImagesRef.current = toolbarImages;

  // Bind the already-rendered figure/socket to a backend model, leaving the
  // DOM, figure, and socket in place so they survive across reruns. Disposes
  // the previously bound model first and records the new cleanup in
  // boundModelCleanupRef, so exactly one model listener is ever attached.
  const bindModel = useCallback(async (id: WidgetModelId): Promise<void> => {
    const fakeWs = wsRef.current;
    if (!fakeWs) {
      return;
    }

    let model: Model<ModelState>;
    try {
      model = await MODEL_MANAGER.get(id);
    } catch {
      Logger.error("Failed to get model for mpl interactive", id);
      return;
    }

    // The figure may have been torn down (unmount, or a structural rebuild)
    // while we awaited the model; don't wire a listener that would outlive it.
    if (wsRef.current !== fakeWs) {
      return;
    }

    // Detach the previously bound model before wiring the new one.
    boundModelCleanupRef.current?.();

    // Re-point outbound traffic at this model without recreating the socket,
    // so mpl.js's onopen/onmessage wiring stays intact.
    const send = (msg: unknown) => model.send(msg);
    fakeWs.setSendHandler(send);
    sendRef.current = send;

    // Listen for backend → frontend messages via model custom events
    const handleCustomMessage = (
      content: { type: string; data?: unknown; format?: string },
      buffers?: readonly DataView[],
    ) => {
      if (!content) {
        return;
      }

      if (content.type === "json") {
        fakeWs.receiveJson(content.data);
      } else if (content.type === "binary" && buffers && buffers.length > 0) {
        fakeWs.receiveBinary(buffers[0]);
      } else if (content.type === "download" && buffers && buffers.length > 0) {
        const fmt = content.format || "png";
        const dv = buffers[0];
        const ab = dv.buffer.slice(
          dv.byteOffset,
          dv.byteOffset + dv.byteLength,
        ) as ArrayBuffer;
        downloadBlob(new Blob([ab], { type: `image/${fmt}` }), `figure.${fmt}`);
      }
    };

    model.on("msg:custom", handleCustomMessage as any);

    // Replay the mpl.js handshake against the new comm so the backend
    // re-establishes image mode and pushes a frame. The figure DOM and the
    // backend manager's toolbar state are left untouched.
    fakeWs.onopen?.();

    boundModelCleanupRef.current = () => {
      model.off("msg:custom", handleCustomMessage as any);
      if (sendRef.current === send) {
        sendRef.current = Functions.NOOP;
      }
    };
  }, []);

  // Mount: build the DOM, mpl figure, and socket once. modelId is read from a
  // ref and intentionally omitted from the deps — rebinding to a new model is
  // handled by the effect below, not by rebuilding the canvas.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    // Clear any previous content (handles re-render / cell re-run)
    container.innerHTML = "";

    // Inject CSS
    const removeCss = injectCss(container, cssUrl);

    // Patch toolbar images
    const removeImageObserver = patchToolbarImages(
      container,
      toolbarImagesRef.current,
    );

    let cancelled = false;

    const setup = async () => {
      // Load mpl.js globally (only once, via <script src>)
      await ensureMplJs(mplJsUrl);

      if (!window.mpl) {
        Logger.error("mpl.js failed to load");
        return;
      }

      // The send handler is swapped per bind; route through sendRef so the
      // socket outlives any single model.
      const fakeWs = new MplCommWebSocket((msg: unknown) => {
        sendRef.current(msg);
      });
      wsRef.current = fakeWs;

      const ondownload = (_figure: MplFigure, format: string) => {
        sendRef.current({ type: "download", format });
      };

      const fig = new window.mpl.figure(
        modelIdRef.current,
        fakeWs,
        ondownload,
        container,
      );
      figureRef.current = fig;

      // Set the canvas_div to the backend's figure size so the
      // ResizeObserver doesn't trigger an immediate resize cycle.
      // mpl.js creates: fig.root > [titlebar, canvas_div, toolbar]
      const canvasDiv = fig.root.querySelector<HTMLElement>("div[tabindex]");
      if (canvasDiv) {
        canvasDiv.style.width = `${width}px`;
        canvasDiv.style.height = `${height}px`;
      }

      await bindModel(modelIdRef.current);
    };

    setup().catch((error) => {
      if (!cancelled) {
        Logger.error("Failed to set up MPL interactive figure", error);
      }
    });

    return () => {
      cancelled = true;
      boundModelCleanupRef.current?.();
      boundModelCleanupRef.current = undefined;
      removeCss();
      removeImageObserver();
      wsRef.current?.close();
      wsRef.current = null;
      figureRef.current = null;
      // Clear DOM on unmount so stale content doesn't linger
      container.innerHTML = "";
    };
  }, [mplJsUrl, cssUrl, width, height, bindModel]);

  // Rebind to a new model when the cell re-runs, keeping the rendered figure
  // and toolbar in place. The initial bind is owned by the mount effect, so
  // skip the first run here.
  const isInitialBindRef = useRef(true);
  useEffect(() => {
    if (isInitialBindRef.current) {
      isInitialBindRef.current = false;
      return;
    }

    // bindModel disposes the previously bound model and guards against a
    // teardown that races the awaited model lookup, so no per-run cleanup is
    // needed here; the mount effect's cleanup detaches the final bind.
    bindModel(modelId).catch((error) => {
      Logger.error("Failed to rebind MPL interactive figure", error);
    });
  }, [modelId, bindModel]);

  // Re-request figure when tab becomes visible
  useEventListener(document, "visibilitychange", () => {
    const fig = figureRef.current;
    if (!document.hidden && fig?.ws?.readyState === WebSocket.OPEN) {
      fig.send_message("refresh", {});
    }
  });

  // Must match _MPL_SCOPE in from_mpl_interactive.py
  return <div ref={containerRef} className={MPL_SCOPE_CLASS} />;
};

export const visibleForTesting = {
  ensureMplJs,
  injectCss,
  MplInteractiveSlot,
  resetMplJsLoading: () => {
    mplJsLoading = null;
  },
};
