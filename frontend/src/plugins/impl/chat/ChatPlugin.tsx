/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { Arrays } from "@/utils/arrays";
import { Chatbot } from "./chat-ui";
import type { ChatMessage, SendMessageRequest } from "./types";

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
export type PluginFunctions = {
  get_chat_history: (req: {}) => Promise<{ messages: ChatMessage[] }>;
  delete_chat_history: (req: {}) => Promise<null>;
  delete_chat_message: (req: { index: number }) => Promise<null>;
  send_prompt: (req: SendMessageRequest) => Promise<string>;
};

export const ChatPlugin = createPlugin<{ messages: ChatMessage[] }>(
  "marimo-chatbot",
)
  .withData(
    z.object({
      prompts: z.array(z.string()).default(Arrays.EMPTY),
      showConfigurationControls: z.boolean(),
      maxHeight: z.number().optional(),
      config: z.object({
        max_tokens: z.number().default(100),
        temperature: z.number().default(0.5),
        top_p: z.number().default(1),
        top_k: z.number().default(40),
        frequency_penalty: z.number().default(0),
        presence_penalty: z.number().default(0),
      }),
      allowAttachments: z.union([z.boolean(), z.string().array()]),
    }),
  )
  .withFunctions<PluginFunctions>({
    get_chat_history: rpc.input(z.object({})).output(
      z.object({
        messages: z.array(
          z.object({
            role: z.enum(["system", "user", "assistant"]),
            content: z.string(),
          }),
        ),
      }),
    ),
    delete_chat_history: rpc.input(z.object({})).output(z.null()),
    delete_chat_message: rpc
      .input(z.object({ index: z.number() }))
      .output(z.null()),
    send_prompt: rpc
      .input(
        z.object({
          messages: z.array(
            z.object({
              role: z.enum(["system", "user", "assistant"]),
              content: z.string(),
              attachments: z
                .array(
                  z.object({
                    name: z.string().optional(),
                    contentType: z.string().optional(),
                    url: z.string(),
                  }),
                )
                .optional(),
            }),
          ),
          config: z.object({
            max_tokens: z.number(),
            temperature: z.number(),
            top_p: z.number(),
            top_k: z.number(),
            frequency_penalty: z.number(),
            presence_penalty: z.number(),
          }),
        }),
      )
      .output(z.string()),
  })
  .renderer((props) => (
    <TooltipProvider>
      <Chatbot
        prompts={props.data.prompts}
        showConfigurationControls={props.data.showConfigurationControls}
        maxHeight={props.data.maxHeight}
        allowAttachments={props.data.allowAttachments}
        config={props.data.config}
        get_chat_history={props.functions.get_chat_history}
        delete_chat_history={props.functions.delete_chat_history}
        delete_chat_message={props.functions.delete_chat_message}
        send_prompt={props.functions.send_prompt}
        value={props.value?.messages || Arrays.EMPTY}
        setValue={(messages) => props.setValue({ messages })}
      />
    </TooltipProvider>
  ));
