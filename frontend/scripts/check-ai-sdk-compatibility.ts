/* Copyright 2026 Marimo. All rights reserved. */

import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { Chat } from "@ai-sdk/react";
import {
  DefaultChatTransport,
  isStaticToolUIPart,
  safeValidateUIMessages,
  type UIMessage,
} from "ai";
import { z } from "zod";

// New SDK part types must get coverage or an explicit unsupported designation.
type FixedPartType = Exclude<
  UIMessage["parts"][number]["type"],
  `tool-${string}` | `data-${string}`
>;
const partCoverage = {
  text: "history",
  reasoning: "history",
  file: "history",
  "source-url": "history",
  "source-document": "history",
  "step-start": "history",
  "dynamic-tool": "history",
  "reasoning-file": "unsupported",
  custom: "unsupported",
} satisfies Record<FixedPartType, "history" | "unsupported">;

const [streamPath, historyPath, scenario] = process.argv.slice(2);
assert(
  streamPath && historyPath && scenario,
  "Expected stream, history, and scenario arguments",
);

for (const name of ["ai", "@ai-sdk/react"]) {
  const packageInfo: unknown = JSON.parse(
    await readFile(
      new URL(`../node_modules/${name}/package.json`, import.meta.url),
      "utf8",
    ),
  );
  assert(
    typeof packageInfo === "object" &&
      packageInfo !== null &&
      "version" in packageInfo &&
      typeof packageInfo.version === "string",
  );
  process.stdout.write(`${name}=${packageInfo.version}\n`);
}
async function checkStream(streamPath: string, historyPath: string) {
  const stream = await readFile(streamPath, "utf8");
  const requests: string[] = [];
  const chat = new Chat({
    transport: new DefaultChatTransport({
      api: "https://chat.test/",
      fetch: async (_url, options) => {
        assert.equal(typeof options?.body, "string");
        requests.push(String(options?.body));
        return new Response(stream, {
          headers: {
            "content-type": "text/event-stream",
            "x-vercel-ai-ui-message-stream": "v1",
          },
        });
      },
    }),
  });

  await chat.sendMessage({ text: "Double two" });
  assert.equal(chat.status, "ready", chat.error?.message);
  const assistant = chat.messages.find(
    (message) => message.role === "assistant",
  );
  assert(assistant, "The SDK did not create an assistant message");
  assert(
    assistant.parts.some(
      (part) => part.type === "reasoning" && part.text.length > 0,
    ),
  );

  if (scenario === "approval" || scenario === "denied") {
    const tool = assistant.parts
      .filter(isStaticToolUIPart)
      .find((part) => part.type === "tool-double");
    assert(tool && tool.state === "approval-requested" && tool.approval);
    await chat.addToolApprovalResponse({
      id: tool.approval.id,
      approved: scenario === "approval",
      reason: scenario === "denied" ? "User declined" : undefined,
    });
    const responded = chat.messages
      .flatMap((message) => message.parts)
      .filter(isStaticToolUIPart)
      .find((part) => part.type === "tool-double");
    assert(responded && responded.state === "approval-responded");
    assert.equal(responded.approval.approved, scenario === "approval");
  } else {
    assert(
      assistant.parts.some(
        (part) => part.type === "text" && part.text.length > 0,
      ),
    );
    assert(
      assistant.parts.some(
        (part) =>
          part.type === "tool-double" &&
          (scenario === "error"
            ? part.state === "output-error" &&
              part.errorText.includes("Cannot double")
            : part.state === "output-available" && part.output === 4),
      ),
    );
  }

  const validation = await safeValidateUIMessages({ messages: chat.messages });
  assert(
    validation.success,
    validation.success ? undefined : validation.error.message,
  );
  await chat.sendMessage({ text: "Continue" });
  assert.equal(chat.status, "ready", chat.error?.message);
  assert.equal(requests.length, 2, "Expected exactly two chat requests");
  await writeFile(historyPath, requests[1] ?? "");
}

async function checkHistory(streamPath: string, historyPath: string) {
  const messagesSchema = z.object({ messages: z.array(z.unknown()) });
  const fixtureSchema = messagesSchema.extend({ name: z.string() });
  const cases = z
    .array(fixtureSchema)
    .parse(JSON.parse(await readFile(streamPath, "utf8")));
  const coveredTypes = new Set(
    cases.flatMap((fixture) =>
      fixture.messages.flatMap((message) => {
        const parsed = z
          .object({ parts: z.array(z.object({ type: z.string() })) })
          .parse(message);
        return parsed.parts.map((part) => part.type);
      }),
    ),
  );
  for (const [type, coverage] of Object.entries(partCoverage)) {
    if (coverage === "history") {
      assert(coveredTypes.has(type), `Missing history coverage for ${type}`);
    }
  }
  const requests: z.infer<typeof fixtureSchema>[] = [];
  for (const fixture of cases) {
    const validation = await safeValidateUIMessages({
      messages: fixture.messages,
    });
    assert(
      validation.success,
      `${fixture.name}: ${validation.success ? "" : validation.error.message}`,
    );
    let submitted = false;
    const chat = new Chat({
      messages: validation.data,
      transport: new DefaultChatTransport({
        api: "https://chat.test/",
        fetch: async (_url, options) => {
          assert.equal(typeof options?.body, "string");
          const request = messagesSchema.parse(
            JSON.parse(String(options?.body)),
          );
          requests.push({ name: fixture.name, messages: request.messages });
          submitted = true;
          return new Response(
            'data: {"type":"start","messageId":"reply"}\n\ndata: {"type":"finish"}\n\ndata: [DONE]\n\n',
            {
              headers: {
                "content-type": "text/event-stream",
                "x-vercel-ai-ui-message-stream": "v1",
              },
            },
          );
        },
      }),
    });
    await chat.sendMessage({ text: "Continue" });
    assert.equal(
      chat.status,
      "ready",
      `${fixture.name}: ${chat.error?.message}`,
    );
    assert(submitted, `${fixture.name}: no request sent`);
  }
  await writeFile(historyPath, JSON.stringify(requests));
}

const check = scenario === "history" ? checkHistory : checkStream;
await check(streamPath, historyPath);
