/* Copyright 2026 Marimo. All rights reserved. */

import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  fileExplorerPanelAtom,
  sessionPanelAtom,
} from "@/components/editor/chrome/panels/panel-accordion-state";
import { openPanel } from "@/components/editor/chrome/state";
import { store } from "@/core/state/jotai";
import { openLensTarget } from "../actions";

vi.mock("@/components/editor/chrome/state", () => ({
  openPanel: vi.fn(),
}));

describe("openLensTarget", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store.set(sessionPanelAtom, {
      openSections: ["variables"],
      hasUserInteracted: false,
    });
    store.set(fileExplorerPanelAtom, {
      openSections: ["files"],
      hasUserInteracted: true,
    });
  });

  it.each(["table", "connection"] as const)(
    "opens the variables panel and expands datasources for a %s",
    (kind) => {
      openLensTarget(kind);

      expect(openPanel).toHaveBeenCalledWith("variables");
      expect(store.get(sessionPanelAtom).openSections).toEqual([
        "variables",
        "datasources",
      ]);
    },
  );

  it("opens the files panel and expands remote storage for a bucket", () => {
    openLensTarget("bucket");

    expect(openPanel).toHaveBeenCalledWith("files");
    expect(store.get(fileExplorerPanelAtom).openSections).toEqual([
      "files",
      "remote-storage",
    ]);
  });

  it("opens the cache panel for a cache", () => {
    openLensTarget("cache");

    expect(openPanel).toHaveBeenCalledWith("cache");
    expect(store.get(sessionPanelAtom).openSections).toEqual(["variables"]);
    expect(store.get(fileExplorerPanelAtom).openSections).toEqual(["files"]);
  });

  it("does not duplicate an already-open section or mark interaction", () => {
    openLensTarget("table");
    openLensTarget("table");

    const state = store.get(sessionPanelAtom);
    expect(state.openSections).toEqual(["variables", "datasources"]);
    expect(state.hasUserInteracted).toBe(false);
  });
});
