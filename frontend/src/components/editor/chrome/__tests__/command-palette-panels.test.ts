/* Copyright 2026 Marimo. All rights reserved. */

import { describe, expect, it } from "vitest";
import type { Capabilities } from "@/core/kernel/messages";
import { getCommandPalettePanelBehavior, PANEL_MAP } from "../types";

const capabilities: Capabilities = {
  terminal: true,
  sql: true,
  datasets: true,
  secrets: true,
  cache: true,
};

describe("getCommandPalettePanelBehavior", () => {
  it("opens AI settings when AI is disabled", () => {
    const panel = PANEL_MAP.get("ai");
    expect(panel).toBeDefined();
    expect(
      getCommandPalettePanelBehavior({
        panel: panel!,
        capabilities,
        aiEnabled: false,
      }),
    ).toBe("open-ai-settings");
  });

  it("toggles AI panel when AI is enabled", () => {
    const panel = PANEL_MAP.get("ai");
    expect(panel).toBeDefined();
    expect(
      getCommandPalettePanelBehavior({
        panel: panel!,
        capabilities,
        aiEnabled: true,
      }),
    ).toBe("toggle");
  });

  it("hides panels that are unavailable at runtime", () => {
    const panel = PANEL_MAP.get("terminal");
    expect(panel).toBeDefined();
    expect(
      getCommandPalettePanelBehavior({
        panel: panel!,
        capabilities: { ...capabilities, terminal: false },
        aiEnabled: true,
      }),
    ).toBe("hidden");
  });
});
