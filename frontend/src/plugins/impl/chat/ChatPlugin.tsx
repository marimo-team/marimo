/* Copyright 2024 Marimo. All rights reserved. */
import { z } from "zod";
import { createPlugin } from "@/plugins/core/builder";
import { rpc } from "@/plugins/core/rpc";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Chatbot } from "./chat-ui";
import type { ChatMessage, SendMessageRequest } from "./types";
import { Arrays } from "@/utils/arrays";

// eslint-disable-next-line @typescript-eslint/consistent-type-definitions
type PluginFunctions = {
  get_chat_history: () => Promise<{ messages: ChatMessage[] }>;
  send_prompt: (req: SendMessageRequest) => Promise<string>;
};

export const ChatPlugin = createPlugin<ChatMessage[]>("marimo-chatbot")
  .withData(
    z.object({
      prompts: z.array(z.string()).default(Arrays.EMPTY),
      showConfigurationControls: z.boolean(),
      // Config
      maxTokens: z.number(),
      temperature: z.number(),
      topP: z.number(),
      topK: z.number(),
      frequencyPenalty: z.number(),
      presencePenalty: z.number(),
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
        maxTokens={props.data.maxTokens}
        temperature={props.data.temperature}
        topP={props.data.topP}
        topK={props.data.topK}
        frequencyPenalty={props.data.frequencyPenalty}
        presencePenalty={props.data.presencePenalty}
        sendPrompt={props.functions.send_prompt}
        value={props.value || Arrays.EMPTY}
        setValue={props.setValue}
      />
    </TooltipProvider>
  ));
