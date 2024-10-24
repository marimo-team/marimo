/* Copyright 2024 Marimo. All rights reserved. */
/* eslint-disable @typescript-eslint/no-explicit-any */
import { z } from "zod";

import type { IPluginProps } from "@/plugins/types";
import { useEffect, useRef, useState } from "react";
import { useAsyncData } from "@/hooks/useAsyncData";
import { dequal } from "dequal";
import { useOnMount } from "@/hooks/useLifecycle";
import { useDeepCompareMemoize } from "@/hooks/useDeepCompareMemoize";
import { ErrorBanner } from "../common/error-banner";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { Logger } from "@/utils/Logger";
import { useEventListener } from "@/hooks/useEventListener";
import { MarimoIncomingMessageEvent } from "@/core/dom/events";

interface Data {
  extension: string | null;
  docs_json: any;
  render_json: any;
}

type T = Record<string, any>;

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  send_to_widget: <T>(req: { message?: any, buffers?: any }) => Promise<null | undefined>;
};

export const PanelPlugin = createPlugin<T>("marimo-panel")
  .withData(
    z.object({
      extension: z.string().nullable(),
      docs_json: z.any(),
      render_json: z.any()
    }),
  )
  .withFunctions<PluginFunctions>({
    send_to_widget: rpc
      .input(z.object({ message: z.any(), buffers: z.array(z.any()) }))
      .output(z.null().optional()),
  })
  .renderer((props) => <PanelSlot {...props} />);


function isObject(obj: unknown): obj is object {
  const tp = typeof obj
  return tp === "function" || tp === "object" && !!obj
}

function is_nullish(obj: unknown): obj is null | undefined {
  return obj == null
}

function isPlainObject<T>(obj: unknown): obj is {[key: string]: T} {
  return isObject(obj) && (is_nullish(obj.constructor) || obj.constructor === Object)
}

function extract_buffers(value: unknown, buffers: ArrayBuffer[]): any {
  if (Array.isArray(value)) {
    for (const val of value) {
      extract_buffers(val, buffers)
    }
  } else if (value instanceof Map) {
    for (const key of value.keys()) {
      const v = value.get(key)
      extract_buffers(v, buffers)
    }
  } else if (value.to_base64 !== undefined) {
    const {buffer} = value
    const id = buffers.length
    buffers.push(buffer)
    return {id}
  } else if (isPlainObject(value)) {
    for (const key of Object.keys(value)) {
      const replaced = extract_buffers(value[key], buffers)
      if (replaced != null) {
        value[key] = replaced
      }
    }
  }
}

type Props = IPluginProps<T, Data, PluginFunctions>;

const PanelSlot = (props: Props) => {
  const { extension, docs_json, render_json } = props.data;
  const ref = useRef<HTMLDivElement>(null);
  const doc = useRef<any>(null);
  const receiver = useRef<any>(null);
  const [loaded, setLoaded] = useState<boolean>(false);
  const [mounted, setMounted] = useState<boolean>(false);
  const event_buffer = []
  let blocked = false
  let timeout = Date.now()

  useOnMount(() => {
    if (!ref.current) {
      return;
    }
    setMounted(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  });

  useEffect(() => {
    if (extension.length !== 0) {
      const script = document.createElement('script');
      script.innerHTML = extension
      document.head.appendChild(script);
    }

    const checkBokeh = setInterval(() => {
      if (window.Bokeh) {
        setLoaded(true);
        clearInterval(checkBokeh);
      }
    }, 10);

    return () => {
      if (extension.length !== 0) {
	document.head.removeChild(script);
      }
      clearInterval(checkBokeh);
    };
  }, []);

  // Listen to incoming messages
  useEventListener(props.host, MarimoIncomingMessageEvent.TYPE, (e) => {
    const metadata = e.detail.metadata
    const buffers = e.detail.buffers
    const content = e.detail.message.content
    if (content.type === 'ACK') {
      blocked = false
      return
    } else if (content.length) {
      receiver.current.consume(content)
    } else if ((buffers != undefined) && (buffers.length > 0)) {
      receiver.current.consume(buffers[0].buffer)
    } else {
      return
    }
    const comm_msg = receiver.current.message
    if ((comm_msg != null) && (Object.keys(comm_msg.content).length > 0)) {
      doc.current.apply_json_patch(comm_msg.content, comm_msg.buffers)
    }
  });

  const process_events = () => {
    const patch = doc.current.create_json_patch(event_buffer)
    event_buffer.splice(0)
    const message = {...Bokeh.protocol.Message.create("PATCH-DOC", {}, patch)}
    const buffers: ArrayBuffer[] = []
    extract_buffers(message.content, buffers)
    props.functions.send_to_widget({message, buffers})
  }

  const sendEvent = (event) => {
    event_buffer.push(event)
    if ((!blocked || (Date.now() > timeout))) {
      setTimeout(() => process_events(), 50)
      blocked = true
      timeout = Date.now()+5000
    }
  }

  useEffect(() => {
    const embedItems = async () => {
      if (!(loaded && mounted)) {
	return;
      }
      const roots = {}
      for (const model_id of Object.keys(render_json.roots)) {
	const root_id = render_json.roots[model_id]
	const el = ref.current.querySelector(`#${root_id}`)
	roots[model_id] = el
      }
      render_json.roots = roots
      const model_id = Object.keys(roots)[0]
      await Bokeh.embed.embed_items_notebook(docs_json, [render_json]);
      doc.current = Bokeh.index.get_by_id(model_id).model.document
      receiver.current = new Bokeh.protocol.Receiver()

      doc.current.on_change(sendEvent)
    };
    embedItems();
  }, [loaded, mounted]);

  return (
    <div ref={ref}>
      {Object.keys(render_json.roots).map((model_id) => {
        const root_id = render_json.roots[model_id]
	return (
	  <div key={root_id} id={root_id}>
            <div
              data-root-id={root_id}
              style={{ display: 'contents' }}
            />
          </div>
	)
      })}
    </div>
  )
};
