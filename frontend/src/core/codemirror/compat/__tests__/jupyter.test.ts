/* Copyright 2024 Marimo. All rights reserved. */

import { EditorState } from "@codemirror/state";
import { EditorView } from "@codemirror/view";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { toast } from "@/components/ui/use-toast";
import { saveUserConfig } from "@/core/network/requests";
import { store } from "@/core/state/jotai";
import { jupyterHelpExtension } from "../jupyter";

// Mock dependencies
vi.mock("@/core/state/jotai", () => ({
  store: {
    get: vi.fn(),
    set: vi.fn(),
  },
}));

vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
}));

vi.mock("@/core/network/requests", () => ({
  saveUserConfig: vi.fn().mockResolvedValue({}),
}));

describe("jupyterHelpExtension", () => {
  let view: EditorView;

  beforeEach(() => {
    // Reset mocks
    vi.clearAllMocks();

    // Setup basic editor state and view
    const state = EditorState.create({
      doc: "",
      extensions: [jupyterHelpExtension()],
    });
    view = new EditorView({ state });
  });

  it("handles pip install command", () => {
    // Simulate typing !pip install
    view.dispatch({
      changes: { from: 0, insert: "!pip install" },
      selection: { anchor: 12 },
    });

    expect(store.set).toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith({
      title: "Package Installation",
      description: expect.any(Object),
    });
  });

  it("handles uv pip install command", () => {
    view.dispatch({
      changes: { from: 0, insert: "!uv pip install" },
      selection: { anchor: 15 },
    });

    expect(store.set).toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith({
      title: "Package Installation",
      description: expect.any(Object),
    });
  });

  it("handles uv add command", () => {
    view.dispatch({
      changes: { from: 0, insert: "!uv add" },
      selection: { anchor: 7 },
    });

    expect(store.set).toHaveBeenCalled();
    expect(toast).toHaveBeenCalledWith({
      title: "Package Installation",
      description: expect.any(Object),
    });
  });

  it("handles autoreload commands", async () => {
    // @ts-expect-error eh typescript
    store.get.mockReturnValue({ runtime: {} });

    // Test autorun mode
    view.dispatch({
      changes: { from: 0, insert: "%autoreload 2" },
      selection: { anchor: "%autoreload 2".length },
    });

    expect(saveUserConfig).toHaveBeenCalledWith({
      config: expect.objectContaining({
        runtime: { auto_reload: "autorun" },
      }),
    });

    // Test lazy mode
    view.dispatch({
      changes: { from: 0, insert: "%autoreload 1" },
      selection: { anchor: "%autoreload 1".length },
    });

    expect(saveUserConfig).toHaveBeenCalledWith({
      config: expect.objectContaining({
        runtime: { auto_reload: "lazy" },
      }),
    });

    // Test off mode
    view.dispatch({
      changes: { from: 0, insert: "%autoreload 0" },
      selection: { anchor: "%autoreload 0".length },
    });

    expect(saveUserConfig).toHaveBeenCalledWith({
      config: expect.objectContaining({
        runtime: { auto_reload: "off" },
      }),
    });
  });

  it("handles ls command with warning", () => {
    view.dispatch({
      changes: { from: 0, insert: "!ls " },
      selection: { anchor: "!ls ".length },
    });

    expect(toast).toHaveBeenCalledWith({
      title: "Listing files",
      description: expect.any(Object),
    });
  });
});
