/* Copyright 2026 Marimo. All rights reserved. */

import { markdownLanguage } from "@codemirror/lang-markdown";
import { hoverResource, type Resource } from "@marimo-team/codemirror-mcp";
import { createStore } from "jotai";
import { assert, beforeEach, describe, expect, it, vi } from "vitest";
import { MockNotebook } from "@/__mocks__/notebook";
import { getAIContextRegistry } from "@/core/ai/context/context";
import { ErrorContextProvider } from "@/core/ai/context/providers/error";
import { AIContextRegistry } from "@/core/ai/context/registry";
import { CellId } from "@/core/cells/ids";
import { resourceExtension } from "../resources";

vi.mock("@marimo-team/codemirror-mcp", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@marimo-team/codemirror-mcp")>()),
  hoverResource: vi.fn(() => []),
}));

vi.mock("@/core/ai/context/context", () => ({
  getAIContextRegistry: vi.fn(),
}));

describe("resource tooltips", () => {
  const message = '<b>Unexpected response</b> &amp; "details"';
  let provider: ErrorContextProvider;
  let resource: Resource;

  beforeEach(() => {
    vi.clearAllMocks();
    const store = createStore();
    MockNotebook.withErrors(store, [
      {
        cellId: CellId.create(),
        cellName: "Cell 1",
        error: { kind: "exception", name: "RuntimeError", message },
      },
    ]);
    provider = new ErrorContextProvider(store);
    resource = provider.getItems()[1];
    vi.mocked(getAIContextRegistry).mockReturnValue(
      new AIContextRegistry().register(provider),
    );
    resourceExtension({ language: markdownLanguage, store });
  });

  function renderTooltip(item = resource) {
    const options = vi.mocked(hoverResource).mock.calls[0][0];
    assert(options.createTooltip);
    return options.createTooltip(item).dom;
  }

  it("preserves literal text in cell error descriptions", () => {
    const dom = renderTooltip();
    expect(dom.textContent).toBe(message);
    expect(dom.childElementCount).toBe(0);
  });

  it("preserves literal descriptions when a provider is unavailable", () => {
    const dom = renderTooltip({ ...resource, type: "unknown" });
    expect(dom.textContent).toBe(message);
    expect(dom.childElementCount).toBe(0);
  });

  it("falls back to the literal resource name", () => {
    const dom = renderTooltip({
      ...resource,
      description: undefined,
      name: message,
    });
    expect(dom.textContent).toBe(message);
    expect(dom.childElementCount).toBe(0);
  });

  it("preserves literal text in completion info strings", () => {
    vi.spyOn(provider, "formatCompletion").mockReturnValue({
      label: "Error",
      info: message,
    });
    const dom = renderTooltip({ ...resource, description: "Fallback" });
    expect(dom.textContent).toBe(message);
    expect(dom.childElementCount).toBe(0);
  });

  it("preserves literal fallback text when an info renderer returns null", () => {
    vi.spyOn(provider, "formatCompletion").mockReturnValue({
      label: "Error",
      info: () => null,
    });
    const dom = renderTooltip();
    expect(dom.textContent).toBe(message);
    expect(dom.childElementCount).toBe(0);
  });

  it("preserves literal fallback text for async info renderers", () => {
    vi.spyOn(provider, "formatCompletion").mockReturnValue({
      label: "Error",
      info: async () => document.createElement("div"),
    });
    const dom = renderTooltip();
    expect(dom.textContent).toBe(message);
    expect(dom.childElementCount).toBe(0);
  });

  it.each(["element", "tooltip"])("preserves custom %s renderers", (kind) => {
    const dom = document.createElement("strong");
    dom.textContent = "Details";
    vi.spyOn(provider, "formatCompletion").mockReturnValue({
      label: "Error",
      info: () => (kind === "element" ? dom : { dom }),
    });
    expect(renderTooltip()).toBe(dom);
  });
});
