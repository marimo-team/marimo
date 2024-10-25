/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";

import type { IPluginProps } from "@/plugins/types";
import { useEffect, useRef, useState } from "react";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { useEventListener } from "@/hooks/useEventListener";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";
import { MessageSchema, extractBuffers, EventBuffer } from "./utils";
import { useEvent } from "@dnd-kit/utilities";

interface BokehDocument {
  create_json_patch: (events: unknown[]) => unknown;
  apply_json_patch: (content: unknown, buffers: ArrayBuffer[]) => void;
  on_change: (callback: (event: unknown) => void) => void;
  _all_models: Set<string>;
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
              events?: Array<{
                model?: { id?: string };
              }>;
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
  send_to_widget: <T>(req: { message?: any; buffers?: any }) => Promise<
    null | undefined
  >;
};

export const PanelPlugin = createPlugin<T>("marimo-panel")
  .withData(
    z.object({
      extension: z.string().nullable(),
      docs_json: z.record(z.unknown()),
      render_json: z
        .object({
          roots: z.record(z.string()),
        })
        .catchall(z.unknown()),
    }),
  )
  .withFunctions<PluginFunctions>({
    send_to_widget: rpc
      .input(
        z.object({
          message: z.unknown(),
          buffers: z.array(z.instanceof(ArrayBuffer)),
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
  const docRef = useRef<BokehDocument | null>(null);
  const receiverRef = useRef<InstanceType<
    typeof window.Bokeh.protocol.Receiver
  > | null>(null);
  const [loaded, setLoaded] = useState<boolean>(false);
  const [rendered, setRendered] = useState<string | null>(null);

  const processEvents = useEvent(() => {
    if (!eventBufferRef.current || !docRef.current) {
      return;
    }

    const events = eventBufferRef.current.getAndClear();
    const patch = docRef.current.create_json_patch(events);
    const message = {
      ...window.Bokeh.protocol.Message.create("PATCH-DOC", {}, patch),
    };
    const buffers: ArrayBuffer[] = [];
    extractBuffers(message.content, buffers);
    functions.send_to_widget({ message, buffers });
  });

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
  useEventListener(host, MarimoIncomingMessageEvent.TYPE, (e) => {
    if (e.detail.message == null) {
      return;
    }

    const message = MessageSchema.parse(e.detail.message);
    const buffers = e.detail.buffers;
    const receiver = receiverRef.current;
    const doc = docRef.current;

    if (!message.content) {
      return;
    }

    if (!receiver || !doc) {
      return;
    }

    // Handle ACK messages
    if (typeof message.content !== "string") {
      if (eventBufferRef.current && eventBufferRef.current.size() > 0) {
        processEvents();
      }
      return;
    }

    // Handle non-ACK messages
    const content = message.content;
    if (content.length > 0) {
      receiver.consume(content);
    } else if (buffers !== undefined && buffers.length > 0) {
      receiver.consume(buffers[0].buffer);
    } else {
      return;
    }

    const commMessage = receiver.message;
    if (commMessage != null && Object.keys(commMessage.content).length > 0) {
      if (commMessage.content.events !== undefined) {
        commMessage.content.events = commMessage.content.events.filter(
          (e: any) => doc._all_models.has(e.model.id),
        );
      }
      doc.apply_json_patch(commMessage.content, commMessage.buffers);
    }
  });

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
      for (const model_id of Object.keys(renderJson.roots)) {
        const root_id = renderJson.roots[model_id];
        if (ref.current) {
          const el = ref.current.querySelector(`#${root_id}`);
          renderItem.roots[model_id] = el as HTMLElement | null;
        }
      }
      const modelId = Object.keys(renderItem.roots)[0];
      await window.Bokeh.embed.embed_items_notebook(docsJson, [renderItem]);
      docRef.current = window.Bokeh.index.get_by_id(modelId).model.document;
      receiverRef.current = new window.Bokeh.protocol.Receiver();
      docRef.current.on_change((event) => eventBufferRef.current?.add(event));
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

type Props = IPluginProps<T, PanelData, PluginFunctions>;
