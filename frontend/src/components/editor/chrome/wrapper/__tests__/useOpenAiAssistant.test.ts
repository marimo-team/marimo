/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";

const getFeatureFlag = vi.fn<(flag: string) => boolean>();

vi.mock("@/core/config/feature-flag", () => ({
  getFeatureFlag: (flag: string) => getFeatureFlag(flag),
}));

const { resolveAiPanelTab } = await import("../useOpenAiAssistant");

describe("resolveAiPanelTab", () => {
  beforeEach(() => {
    getFeatureFlag.mockReset();
  });

  it("honors an explicit panel regardless of the feature flag", () => {
    getFeatureFlag.mockReturnValue(false);
    expect(resolveAiPanelTab("agents", "chat")).toBe("agents");
    expect(resolveAiPanelTab("chat", "agents")).toBe("chat");
  });

  it("uses the stored tab when external agents are enabled", () => {
    getFeatureFlag.mockReturnValue(true);
    expect(resolveAiPanelTab(undefined, "agents")).toBe("agents");
    expect(resolveAiPanelTab(undefined, "chat")).toBe("chat");
  });

  it("falls back to chat when external agents are disabled", () => {
    getFeatureFlag.mockReturnValue(false);
    // A stale "agents" preference must not strand the prompt.
    expect(resolveAiPanelTab(undefined, "agents")).toBe("chat");
    expect(resolveAiPanelTab(undefined, "chat")).toBe("chat");
  });
});
