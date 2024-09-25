/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Chatbot } from "./chat-ui";
import type { ChatClientMessage, SendMessageRequest } from "./types";

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  get_chat_history: () => Promise<{ messages: ChatClientMessage[] }>;
  send_prompt: (
    req: SendMessageRequest,
    // ) => Promise<{ messages: ChatClientMessage[] }>;
  ) => Promise<string>;
};

// Update the plugin definition
export const ChatPlugin = createPlugin<ChatClientMessage[]>("marimo-chatbot")
  .withData(
    z.object({
      systemMessage: z
        .string()
        .default("You are a helpful assistant specializing in data science."),
      maxTokens: z.number().optional(),
      temperature: z.number().optional(),
      top_p: z.number().optional(),
      top_k: z.number().optional(),
      frequency_penalty: z.number().optional(),
      presence_penalty: z.number().optional(),
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
    send_prompt: rpc
      .input(
        z.object({
          messages: z.array(
            z.object({
              role: z.enum(["system", "user", "assistant"]),
              content: z.string(),
            }),
          ),
          config: z.object({
            max_tokens: z.number().optional(),
            temperature: z.number().optional(),
            top_p: z.number().optional(),
            top_k: z.number().optional(),
            frequency_penalty: z.number().optional(),
            presence_penalty: z.number().optional(),
          }),
        }),
      )
      .output(
        z.string(),
        // z.object({
        //   messages: z.array(
        //     z.object({
        //       role: z.enum(["system", "user", "assistant"]),
        //       content: z.string(),
        //     }),
        //   ),
        // }),
      ),
  })
  .renderer((props) => (
    <TooltipProvider>
      <Chatbot
        systemMessage={props.data.systemMessage}
        maxTokens={props.data.maxTokens}
        temperature={props.data.temperature}
        getChatHistory={props.functions.get_chat_history}
        sendPrompt={props.functions.send_prompt}
        value={props.value}
        setValue={props.setValue}
      />
    </TooltipProvider>
  ));
