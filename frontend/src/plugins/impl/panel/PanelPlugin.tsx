/* Copyright 2026 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */

import { useCallback, useEffect, useRef, useState } from "react";
import { z } from "zod";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import {
  type HTMLElementNotDerivedFromRef,
  useEventListener,
} from "@/hooks/useEventListener";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import type { IPluginProps } from "@/plugins/types";
import { Logger } from "@/utils/Logger";
import { EventBuffer, extractBuffers, MessageSchema } from "./utils";

interface BokehDocument {
  create_json_patch: (events: unknown[]) => unknown;
  apply_json_patch: (content: unknown, buffers: ArrayBuffer[]) => void;
  on_change: (callback: (event: unknown) => void) => void;
  _all_models: Map<string, unknown>;
}

interface RenderItems {
  roots: Record<string, HTMLElement | null>;
  [key: string]: unknown;
}

declare global {
  interface Window {
    Bokeh: {
      embed: {
        embed_items_notebook: (
          docs_json: Record<string, unknown>,
          render_items: unknown[],
        ) => Promise<void>;
      };
      index: {
        get_by_id: (id: string) => { model: { document: BokehDocument } };
      };
      protocol: {
        Message: {
          create: (
            type: string,
            metadata: Record<string, unknown>,
            content: unknown,
          ) => Record<string, unknown>;
        };
        Receiver: new () => {
          consume: (data: ArrayBuffer | string) => void;
          message: {
            content: {
              events?: {
                model?: { id?: string };
              }[];
              [key: string]: unknown;
            };
            buffers: ArrayBuffer[];
          } | null;
        };
      };
    };
  }
}

interface PanelData {
  extension: string | null;
  docs_json: Record<string, unknown>;
  render_json: {
    roots: Record<string, string>;
    [key: string]: unknown;
  };
}

type T = Record<string, unknown>;

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  send_to_widget: <T>(req: {
    message?: unknown;
    buffers?: unknown;
  }) => Promise<null | undefined>;
};

export const PanelPlugin = createPlugin<T>("marimo-panel")
  .withData(
    z.object({
      extension: z.string().nullable(),
      docs_json: z.record(z.string(), z.unknown()),
      render_json: z
        .object({
          roots: z.record(z.string(), z.string()),
        })
        .catchall(z.unknown()),
    }),
  )
  .withFunctions<PluginFunctions>({
    send_to_widget: rpc
      .input(
        z.object({
          message: z.unknown(),
          buffers: z.array(z.string()),
        }),
      )
      .output(z.null().optional()),
  })
  .renderer((props) => <PanelSlot {...props} />);

function isBokehLoaded() {
  return window.Bokeh != null;
}

const PanelSlot = (props: Props) => {
  const { data, functions, host } = props;
  const { extension, docs_json: docsJson, render_json: renderJson } = data;
  const ref = useRef<HTMLDivElement>(null);
  const rootModelIdRef = useRef<string | null>(null);
  const receiverRef = useRef<InstanceType<
    typeof window.Bokeh.protocol.Receiver
  > | null>(null);
  const [loaded, setLoaded] = useState<boolean>(false);
  const [rendered, setRendered] = useState<string | null>(null);

  // Store functions in a ref so the callback captured by EventBuffer stays current
  const functionsRef = useRef(functions);
  functionsRef.current = functions;

  const processEvents = useCallback(() => {
    if (!eventBufferRef.current) {
      return;
    }

    const events = eventBufferRef.current.getAndClear();
    if (events.length === 0) {
      return;
    }

    // Use the event's own document — it is always current, even when
    // DynamicMap/HoloViews has replaced the document after embedding.
    const firstEvent = events.at(0);
    if (!isDocumentEvent(firstEvent)) {
      return;
    }
    const doc = firstEvent.document;

    // Keep only events that belong to this document
    const sameDocEvents = events.filter(
      (ev) => isDocumentEvent(ev) && ev.document === doc,
    );

    const patch = doc.create_json_patch(sameDocEvents);
    const message = window.Bokeh.protocol.Message.create(
      "PATCH-DOC",
      {},
      patch,
    );
    const buffers: ArrayBuffer[] = [];
    message.content = extractBuffers(message.content, buffers);
    functionsRef.current.send_to_widget({ message, buffers }).catch((error) => {
      Logger.warn("Failed to send Panel event to backend", error);
    });
  }, []);

  const eventBufferRef = useRef<EventBuffer<unknown> | null>(
    new EventBuffer(processEvents),
  );

  // Load the bokeh extension
  useEffect(() => {
    // Already loaded
    if (isBokehLoaded()) {
      setLoaded(true);
      return;
    }

    // Load the extension
    if (extension) {
      const script = document.createElement("script");
      script.innerHTML = extension;
      document.head.append(script);
    }

    // Check if Bokeh is loaded every 10ms
    const checkBokeh = setInterval(() => {
      if (isBokehLoaded()) {
        setLoaded(true);
        clearInterval(checkBokeh);
      }
    }, 10);

    return () => clearInterval(checkBokeh);
  }, [extension, setLoaded]);

  // Listen for incoming messages
  useEventListener(
    host as HTMLElementNotDerivedFromRef,
    MarimoIncomingMessageEvent.TYPE,
    (e) => {
      if (e.detail.message == null) {
        return;
      }

      const message = MessageSchema.parse(e.detail.message);
      const buffers = e.detail.buffers;
      const receiver = receiverRef.current;

      if (!receiver) {
        return;
      }

      const content = message.content;
      if (content !== null && typeof message.content !== "string") {
        // Handle ACK messages
        if (eventBufferRef.current && eventBufferRef.current.size() > 0) {
          processEvents();
        }
        return;
      }

      const doc = getDoc(rootModelIdRef.current);
      if (!doc) {
        return;
      }

      if (buffers && buffers.length > 0) {
        // Check if we already have an ArrayBuffer
        const buffer = buffers[0];
        if (buffer instanceof ArrayBuffer) {
          receiver.consume(buffer);
        } else if (buffer.buffer instanceof ArrayBuffer) {
          // If we have an ArrayBufferView, use its buffer
          receiver.consume(buffer.buffer);
        }
      } else if (content && typeof content === "string") {
        receiver.consume(content);
      } else {
        return;
      }

      const commMessage = receiver.message;
      if (commMessage != null && Object.keys(commMessage.content).length > 0) {
        if (commMessage.content.events !== undefined) {
          commMessage.content.events = commMessage.content.events.filter(
            (e) => e?.model?.id && doc._all_models.has(e.model.id),
          );
        }
        doc.apply_json_patch(commMessage.content, commMessage.buffers);
      }
    },
  );

  // Embed the items on the first render
  useEffect(() => {
    const docId = Object.keys(docsJson)[0];

    // Skip if not loaded or already rendered
    if (!loaded || rendered === docId) {
      return;
    }

    const embedItems = async () => {
      const renderItem: RenderItems = {
        ...renderJson,
        roots: {},
      };
      for (const modelId of Object.keys(renderJson.roots)) {
        const rootId = renderJson.roots[modelId];
        if (ref.current) {
          const el = ref.current.querySelector(`#${rootId}`);
          renderItem.roots[modelId] = el as HTMLElement | null;
        }
      }
      const modelId = Object.keys(renderItem.roots)[0];
      await window.Bokeh.embed.embed_items_notebook(docsJson, [renderItem]);
      rootModelIdRef.current = modelId;
      const doc = window.Bokeh.index.get_by_id(modelId).model.document;
      receiverRef.current = new window.Bokeh.protocol.Receiver();
      doc.on_change((event) => {
        // Bokeh tags server-applied patch events with sync=false via
        // model.setv({...}, {sync: false}) inside apply_json_patch.
        // Only forward user-initiated events (sync=true, the default).
        if (isSyncEvent(event) && event.sync) {
          eventBufferRef.current?.add(event);
        }
      });
      setRendered(docId);
    };

    embedItems();
  }, [docsJson, loaded, renderJson, rendered]);

  return (
    <div ref={ref}>
      {Object.values(renderJson.roots).map((rootId) => (
        <div key={rootId} id={rootId}>
          <div data-root-id={rootId} style={{ display: "contents" }} />
        </div>
      ))}
    </div>
  );
};

// Re-fetch the live document from the Bokeh index. DynamicMap/HoloViews
// may replace the document after initial embedding, so a stale ref would
// cause "Cannot create a patch using events from a different document".
function getDoc(id: string | null): BokehDocument | null {
  if (!id) {
    return null;
  }
  try {
    return window.Bokeh.index.get_by_id(id).model.document;
  } catch (error) {
    Logger.warn("Failed to get Bokeh document", error);
    return null;
  }
}

function isSyncEvent(x: unknown): x is { sync: boolean } {
  const isObject = !!x && typeof x === "object";
  return isObject && "sync" in x;
}

function isDocumentEvent(x: unknown): x is { document: BokehDocument } {
  const isObject = !!x && typeof x === "object";
  return isObject && "document" in x;
}

type Props = IPluginProps<T, PanelData, PluginFunctions>;
