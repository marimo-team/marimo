/* Copyright 2026 Marimo. All rights reserved. */

import type { UIMessage } from "ai";
import { Suspense } from "react";
import { z } from "zod";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { Arrays } from "@/utils/arrays";
import { Chatbot } from "./chat-ui";
import type { SendMessageRequest } from "./types";

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
export type PluginFunctions = {
  get_chat_history: (req: {}) => Promise<{ messages: UIMessage[] }>;
  delete_chat_history: (req: {}) => Promise<null>;
  delete_chat_message: (req: { index: number }) => Promise<null>;
  send_prompt: (req: SendMessageRequest) => Promise<unknown>;
};

const messageSchema = z.array(
  z.object({
    id: z.string(),
    role: z.enum(["system", "user", "assistant"]),
    content: z.string().nullable(),
    parts: z.array(z.any()),
    metadata: z.any().nullable(),
  }),
);

const configSchema = z.object({
  max_tokens: z.number().nullable(),
  temperature: z.number().nullable(),
  top_p: z.number().nullable(),
  top_k: z.number().nullable(),
  frequency_penalty: z.number().nullable(),
  presence_penalty: z.number().nullable(),
});

export const ChatPlugin = createPlugin<{ messages: UIMessage[] }>(
  "marimo-chatbot",
)
  .withData(
    z.object({
      prompts: z.array(z.string()).default(Arrays.EMPTY),
      showConfigurationControls: z.boolean(),
      maxHeight: z.number().optional(),
      config: configSchema,
      allowAttachments: z.union([z.boolean(), z.string().array()]),
      disabled: z.boolean().default(false),
    }),
  )
  .withFunctions<PluginFunctions>({
    get_chat_history: rpc.input(z.object({})).output(
      z.object({
        messages: messageSchema,
      }),
    ),
    delete_chat_history: rpc.input(z.object({})).output(z.null()),
    delete_chat_message: rpc
      .input(z.object({ index: z.number() }))
      .output(z.null()),
    send_prompt: rpc
      .input(
        z.object({
          messages: messageSchema,
          config: configSchema,
        }),
      )
      .output(z.unknown()),
  })
  .renderer((props) => (
    <TooltipProvider>
      <Suspense>
        <Chatbot
          prompts={props.data.prompts}
          showConfigurationControls={props.data.showConfigurationControls}
          maxHeight={props.data.maxHeight}
          allowAttachments={props.data.allowAttachments}
          disabled={props.data.disabled}
          config={props.data.config}
          get_chat_history={props.functions.get_chat_history}
          delete_chat_history={props.functions.delete_chat_history}
          delete_chat_message={props.functions.delete_chat_message}
          send_prompt={props.functions.send_prompt}
          value={props.value?.messages || Arrays.EMPTY}
          setValue={(messages) => props.setValue({ messages })}
          host={props.host}
        />
      </Suspense>
    </TooltipProvider>
  ));
