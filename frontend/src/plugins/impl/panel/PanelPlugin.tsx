/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";

import type { IPluginProps } from "@/plugins/types";
import { useEffect, useRef, useState } from "react";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { useEventListener } from "@/hooks/useEventListener";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";

interface Data {
  extension: string | null;
  docs_json: Record<string, any>;
  render_json: Record<string, any>;
}

type T = Record<string, any>;

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  send_to_widget: <T>(req: { message?: any; buffers?: any }) => Promise<
    null | undefined
  >;
};

declare global {
  const Bokeh: any;
}

export const PanelPlugin = createPlugin<T>("marimo-panel")
  .withData(
    z.object({
      extension: z.string().nullable(),
      docs_json: z.record(z.any()),
      render_json: z.record(z.any()),
    }),
  )
  .withFunctions<PluginFunctions>({
    send_to_widget: rpc
      .input(z.object({ message: z.any(), buffers: z.array(z.any()) }))
      .output(z.null().optional()),
  })
  .renderer((props) => <PanelSlot {...props} />);

function isObject(obj: unknown): obj is object {
  const tp = typeof obj;
  return tp === "function" || (tp === "object" && !!obj);
}

function is_nullish(obj: unknown): obj is null | undefined {
  return obj == null;
}

function isPlainObject<T>(obj: unknown): obj is { [key: string]: T } {
  return (
    isObject(obj) && (is_nullish(obj.constructor) || obj.constructor === Object)
  );
}

function isBuffer(obj: unknown): obj is { buffer: ArrayBuffer } {
  return typeof obj === "object" && obj !== null && "to_base64" in obj;
}
function extract_buffers(value: unknown, buffers: ArrayBuffer[]): any {
  if (Array.isArray(value)) {
    for (const val of value) {
      extract_buffers(val, buffers);
    }
  } else if (value instanceof Map) {
    for (const key of value.keys()) {
      const v = value.get(key);
      extract_buffers(v, buffers);
    }
  } else if (isBuffer(value)) {
    const { buffer } = value;
    const id = buffers.length;
    buffers.push(buffer);
    return { id };
  } else if (isPlainObject(value)) {
    for (const key of Object.keys(value)) {
      const replaced = extract_buffers(value[key], buffers);
      if (replaced != null) {
        value[key] = replaced;
      }
    }
  }
}

type Props = IPluginProps<T, Data, PluginFunctions>;

const PanelSlot = (props: Props) => {
  const { data, functions, host } = props;
  const { extension, docs_json, render_json } = data;
  const ref = useRef<HTMLDivElement>(null);
  const blocked = useRef<boolean>(false);
  const doc = useRef<any>(null);
  const receiver = useRef<any>(null);
  const [loaded, setLoaded] = useState<boolean>(false);
  const [rendered, setRendered] = useState<string | null>(null);

  const event_buffer: any[] = [];
  let timeout = Date.now();

  const process_events = () => {
    const events = event_buffer.splice(0);
    const patch = doc.current.create_json_patch(events);
    const message = {
      ...Bokeh.protocol.Message.create("PATCH-DOC", {}, patch),
    };
    const buffers: ArrayBuffer[] = [];
    extract_buffers(message.content, buffers);
    functions.send_to_widget({ message, buffers });
  };

  useEffect(() => {
    if (loaded || rendered) {
      return;
    }
    let script: HTMLScriptElement;
    if (extension != null && extension.length > 0) {
      script = document.createElement("script");
      script.innerHTML = extension;
      document.head.append(script);
    }

    const checkBokeh = setInterval(() => {
      if (window.Bokeh) {
        setLoaded(true);
        clearInterval(checkBokeh);
      }
    }, 10);

    return () => {
      clearInterval(checkBokeh);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [extension]);

  // Listen to incoming messages
  useEventListener(host, MarimoIncomingMessageEvent.TYPE, (e) => {
    // const doc_id = Object.keys(docs_json)[0];
    // const metadata = e.detail.metadata;
    const buffers = e.detail.buffers;
    if (e.detail.message == null) {
      return;
    }
    const message = MessageSchema.parse(e.detail.message);
    if (message.content.type === "ACK") {
      if (event_buffer.length > 0) {
        process_events();
        timeout = Date.now();
      } else {
        blocked.current = false;
      }
      return;
    }
    const content = message.content;
    if (content.length > 0) {
      receiver.current.consume(content);
    } else if (buffers !== undefined && buffers.length > 0) {
      receiver.current.consume(buffers[0].buffer);
    } else {
      return;
    }
    const comm_msg = receiver.current.message;
    if (comm_msg != null && Object.keys(comm_msg.content).length > 0) {
      if (comm_msg.content.events !== undefined) {
        comm_msg.content.events = comm_msg.content.events.filter((e: any) =>
          doc.current._all_models.has(e.model.id),
        );
      }
      doc.current.apply_json_patch(comm_msg.content, comm_msg.buffers);
    }
  });

  useEffect(() => {
    const doc_id = Object.keys(docs_json)[0];
    if (!loaded || rendered === doc_id) {
      return;
    }
    event_buffer.length = 0;

    const sendEvent = (event: any) => {
      event_buffer.push(event);
      if (!blocked.current || Date.now() > timeout) {
        setTimeout(() => process_events(), 50);
        blocked.current = true;
        // eslint-disable-next-line react-hooks/exhaustive-deps
        timeout = Date.now() + 5000;
      }
    };

    const embedItems = async () => {
      const render_item = { ...render_json };
      const roots: Record<string, HTMLElement | null> = {};
      for (const model_id of Object.keys(render_json.roots)) {
        const root_id = render_json.roots[model_id];
        if (ref.current) {
          const el = ref.current.querySelector(`#${root_id}`);
          roots[model_id] = el as HTMLElement | null;
        }
      }
      render_item.roots = roots;
      const model_id = Object.keys(roots)[0];
      await Bokeh.embed.embed_items_notebook(docs_json, [render_item]);
      doc.current = Bokeh.index.get_by_id(model_id).model.document;
      receiver.current = new Bokeh.protocol.Receiver();
      doc.current.on_change(sendEvent);
      setRendered(doc_id);
    };
    embedItems();
  }, [docs_json, functions, loaded, render_json, rendered]);

  return (
    <div ref={ref}>
      {Object.keys(render_json.roots).map((model_id) => {
        const root_id = render_json.roots[model_id];
        return (
          <div key={root_id} id={root_id}>
            <div data-root-id={root_id} style={{ display: "contents" }} />
          </div>
        );
      })}
    </div>
  );
};

const MessageSchema = z.object({
  content: z.any(),
});
