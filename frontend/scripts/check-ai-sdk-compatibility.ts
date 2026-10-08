/* Copyright 2026 Marimo. All rights reserved. */

import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { Chat } from "@ai-sdk/react";
import {
  DefaultChatTransport,
  isStaticToolUIPart,
  safeValidateUIMessages,
} from "ai";

const [streamPath, historyPath, scenario] = process.argv.slice(2);
assert(
  streamPath && historyPath && scenario,
  "Expected stream, history, and scenario arguments",
);
const stream = await readFile(streamPath, "utf8");
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
const assistant = chat.messages.find((message) => message.role === "assistant");
assert(assistant, "The SDK did not create an assistant message");
assert(
  assistant.parts.some(
    (part) => part.type === "reasoning" && part.text.length > 0,
  ),
);

if (scenario === "approval") {
  const tool = assistant.parts
    .filter(isStaticToolUIPart)
    .find((part) => part.type === "tool-double");
  assert(tool && tool.state === "approval-requested" && tool.approval);
  await chat.addToolApprovalResponse({ id: tool.approval.id, approved: true });
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
        part.state === "output-available" &&
        part.output === 4,
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
