/* Copyright 2026 Marimo. All rights reserved. */

import { afterEach, expect, it, vi } from "vitest";
import { listProviderModels } from "../ai";

vi.mock("@/core/runtime/config", () => ({
  getRuntimeManager: () => ({
    httpURL: new URL("https://notebook.example.com/nested/"),
    headers: () => ({ "Marimo-Session-Id": "session" }),
  }),
}));

afterEach(() => vi.unstubAllGlobals());

it.each([
  ["gateway", "gateway"],
  ["gateway?tenant", "gateway%3Ftenant"],
  ["gateway#tenant", "gateway%23tenant"],
])(
  "encodes %s while preserving runtime URL prefix and session headers",
  async (provider, encodedProvider) => {
    const catalog = { models: [{ id: "model", name: "Model" }] };
    const fetch = vi
      .fn<(request: Request) => Promise<Response>>()
      .mockResolvedValue(Response.json(catalog));
    vi.stubGlobal("fetch", fetch);

    await expect(listProviderModels(provider)).resolves.toEqual(catalog);
    expect(fetch).toHaveBeenCalledOnce();
    const [request] = fetch.mock.calls[0];
    expect({
      method: request.method,
      url: request.url,
      session: request.headers.get("Marimo-Session-Id"),
    }).toEqual({
      method: "GET",
      url: `https://notebook.example.com/nested/api/ai/models/${encodedProvider}`,
      session: "session",
    });
  },
);
