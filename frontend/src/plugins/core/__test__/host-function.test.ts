/* Copyright 2026 Marimo. All rights reserved. */

import type { NotebookClient } from "@marimo-team/client";
import { afterEach, expect, it, vi } from "vitest";
import { z } from "zod";
import { createHostFunctionRequest } from "@/core/functions/host-function";
import { Deferred } from "@/utils/Deferred";
import { callPluginFunction } from "../function-call";

const success = {
  ok: true,
  status: 200,
  data: {
    request_id: "r1",
    result: {
      status: { code: "ok", title: null, message: null },
      return_value: { rows: [1] },
      found: true,
    },
  },
} as const;

function setup() {
  const lifetime = new AbortController();
  const sendUIElement = vi
    .fn<NotebookClient["sendUIElement"]>()
    .mockResolvedValue(success);
  const request = createHostFunctionRequest({ sendUIElement }, lifetime.signal);
  let namespace = "c1-0";
  const call = (args: unknown = undefined) =>
    callPluginFunction({
      name: "search",
      args: args ?? { query: "a" },
      input: z.object({ query: z.string() }),
      output: z.object({ rows: z.array(z.number()) }),
      getNamespace: () => namespace,
      request,
    });
  return {
    lifetime,
    sendUIElement,
    call,
    setNamespace: (value: string) => {
      namespace = value;
    },
  };
}

afterEach(() => vi.useRealTimers());

it("keeps the existing function arguments and validates the result", async () => {
  const s = setup();
  expect(await s.call()).toEqual({ rows: [1] });
  expect(s.sendUIElement).toHaveBeenCalledWith(
    "c1-0",
    { function: "search", args: { query: "a" } },
    { signal: s.lifetime.signal },
  );
});

it("rejects invalid arguments before sending", async () => {
  const s = setup();
  await expect(s.call({ query: 42 })).rejects.toThrow("expected string");
  expect(s.sendUIElement).not.toHaveBeenCalled();
});

it("rejects invalid output without retrying a completed call", async () => {
  const s = setup();
  s.sendUIElement.mockResolvedValue({
    ...success,
    data: {
      ...success.data,
      result: { ...success.data.result, return_value: { rows: "invalid" } },
    },
  });
  await expect(s.call()).rejects.toThrow("expected array");
  expect(s.sendUIElement).toHaveBeenCalledTimes(1);
});

it("retries only missing registrations and rereads the object id", async () => {
  vi.useFakeTimers();
  const s = setup();
  s.sendUIElement.mockResolvedValueOnce({
    ...success,
    data: {
      ...success.data,
      result: {
        ...success.data.result,
        found: false,
        status: { code: "error", title: "Missing", message: null },
      },
    },
  });
  const pending = s.call();
  s.setNamespace("c1-1");
  await vi.runAllTimersAsync();
  expect(await pending).toEqual({ rows: [1] });
  expect(s.sendUIElement.mock.calls.map(([id]) => id)).toEqual([
    "c1-0",
    "c1-1",
  ]);
});

it("does not retry function errors or transport problems", async () => {
  const s = setup();
  s.sendUIElement.mockResolvedValueOnce({
    ...success,
    data: {
      ...success.data,
      result: {
        ...success.data.result,
        status: { code: "error", title: "Failed", message: "function failed" },
      },
    },
  });
  await expect(s.call()).rejects.toThrow("function failed");
  expect(s.sendUIElement).toHaveBeenCalledTimes(1);
  s.sendUIElement.mockResolvedValueOnce({
    ok: false,
    status: 504,
    problem: {
      type: "tag:marimo.io,2026:host/timeout",
      title: "Result timeout",
      status: 504,
    },
  });
  await expect(s.call()).rejects.toThrow("Result timeout");
  expect(s.sendUIElement).toHaveBeenCalledTimes(2);
});

it("rejects stale results and further calls after the element lifetime ends", async () => {
  const s = setup();
  const reply = new Deferred<
    Awaited<ReturnType<NotebookClient["sendUIElement"]>>
  >();
  s.sendUIElement.mockReturnValue(reply.promise);
  const pending = s.call();
  s.lifetime.abort(new Error("element replaced"));
  reply.resolve(success);
  await expect(pending).rejects.toThrow("element replaced");
  await expect(s.call()).rejects.toThrow("element replaced");
  expect(s.sendUIElement).toHaveBeenCalledTimes(1);
});
