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

  const setupFigure = useCallback(
    async (container: HTMLElement) => {
      // Load mpl.js globally (only once, via <script src>)
      await ensureMplJs(mplJsUrl);

      if (!window.mpl) {
        Logger.error("mpl.js failed to load");
        return;
      }

      // Get the model from MODEL_MANAGER
      let model: Model<ModelState>;
      try {
        model = await MODEL_MANAGER.get(modelId);
      } catch {
        Logger.error("Failed to get model for mpl interactive", modelId);
        return;
      }

      // Create the fake WebSocket
      const fakeWs = new MplCommWebSocket((msg: unknown) => {
        // Send from frontend → backend via model custom message
        model.send(msg);
      });
      wsRef.current = fakeWs;

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
        } else if (
          content.type === "download" &&
          buffers &&
          buffers.length > 0
        ) {
          const fmt = content.format || "png";
          const dv = buffers[0];
          const ab = dv.buffer.slice(
            dv.byteOffset,
            dv.byteOffset + dv.byteLength,
          ) as ArrayBuffer;
          downloadBlob(
            new Blob([ab], { type: `image/${fmt}` }),
            `figure.${fmt}`,
          );
        }
      };

      model.on("msg:custom", handleCustomMessage as any);

      // Create the mpl figure
      const figId = modelId;
      const ondownload = (_figure: MplFigure, format: string) => {
        // Send download request to backend
        model.send({ type: "download", format });
      };

      const fig = new window.mpl.figure(figId, fakeWs, ondownload, container);
      figureRef.current = fig;

      // Set the canvas_div to the backend's figure size so the
      // ResizeObserver doesn't trigger an immediate resize cycle.
      // mpl.js creates: fig.root > [titlebar, canvas_div, toolbar]
      const canvasDiv = fig.root.querySelector<HTMLElement>("div[tabindex]");
      if (canvasDiv) {
        canvasDiv.style.width = `${width}px`;
        canvasDiv.style.height = `${height}px`;
      }

      // Trigger the onopen callback to start communication
      // mpl.js sends initial messages in onopen
      setTimeout(() => {
        fakeWs.onopen?.();
      }, 0);

      return () => {
        model.off("msg:custom", handleCustomMessage as any);
        fakeWs.close();
      };
    },
    [modelId, mplJsUrl, width, height],
  );

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
    const removeImageObserver = patchToolbarImages(container, toolbarImages);

    let cleanup: (() => void) | undefined;
    let cancelled = false;

    setupFigure(container)
      .then((cleanupFn) => {
        if (cancelled) {
          cleanupFn?.();
          return;
        }
        cleanup = cleanupFn;
      })
      .catch((error) => {
        if (!cancelled) {
          Logger.error("Failed to set up MPL interactive figure", error);
        }
      });

    return () => {
      cancelled = true;
      removeCss();
      removeImageObserver();
      cleanup?.();
      // Clear DOM on unmount so stale content doesn't linger
      container.innerHTML = "";
    };
  }, [modelId, cssUrl, toolbarImages, setupFigure]);

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
  resetMplJsLoading: () => {
    mplJsLoading = null;
  },
};
