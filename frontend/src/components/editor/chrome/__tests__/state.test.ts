/* Copyright 2026 Marimo. All rights reserved. */
import { describe, expect, it } from "vitest";
import { adaptForLocalStorage } from "@/utils/storage/jotai";
import type { PanelLayout } from "../state";
import { exportedForTesting } from "../state";

const { mergePanelLayout } = exportedForTesting;

describe("mergePanelLayout", () => {
  // Exact localStorage value from SageMaker Studio that caused the bug:
  // saved before Terminal was added, so "terminal" is absent from
  // developerPanel and the tab never renders.
  it("appends terminal to a pre-terminal-era saved layout", () => {
    const saved: PanelLayout = {
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "snippets",
        "logs",
      ],
    };
    expect(mergePanelLayout(saved)).toEqual({
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "snippets",
        "logs",
        "terminal",
      ],
    });
  });

  it("appends new sidebar panels missing from saved layout", () => {
    const saved: PanelLayout = {
      sidebar: ["files", "variables"],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "logs",
        "terminal",
        "snippets",
      ],
    };
    expect(mergePanelLayout(saved)).toEqual({
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "logs",
        "terminal",
        "snippets",
      ],
    });
  });

  it("appends new developer panel entries missing from saved layout", () => {
    const saved: PanelLayout = {
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: ["errors", "scratchpad", "tracing", "logs"],
    };
    expect(mergePanelLayout(saved)).toEqual({
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "logs",
        "secrets",
        "terminal",
        "snippets",
      ],
    });
  });

  it("does not duplicate panels already present", () => {
    const saved: PanelLayout = {
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "logs",
        "terminal",
        "snippets",
      ],
    };
    expect(mergePanelLayout(saved)).toEqual({
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "logs",
        "terminal",
        "snippets",
      ],
    });
  });

  it("preserves panels the user moved between sections", () => {
    const saved: PanelLayout = {
      sidebar: ["files"],
      developerPanel: ["errors", "variables"],
    };
    expect(mergePanelLayout(saved)).toEqual({
      sidebar: [
        "files",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "variables",
        "scratchpad",
        "tracing",
        "secrets",
        "logs",
        "terminal",
        "snippets",
      ],
    });
  });

  it("handles empty saved layout", () => {
    const saved: PanelLayout = {
      sidebar: [],
      developerPanel: [],
    };
    expect(mergePanelLayout(saved)).toEqual({
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "logs",
        "terminal",
        "snippets",
      ],
    });
  });
});

describe("panelLayoutStorage integration", () => {
  it("merges missing panels when reading from localStorage", () => {
    // Simulate the exact SageMaker bug: stale layout in localStorage
    const staleLayout: PanelLayout = {
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "snippets",
        "logs",
      ],
    };

    // Mock localStorage with the stale value
    const mockStorage: Storage = {
      length: 1,
      key: () => null,
      clear: () => undefined,
      removeItem: () => undefined,
      setItem: () => undefined,
      getItem: (key: string) => {
        if (key === "marimo:panel-layout") {
          return JSON.stringify(staleLayout);
        }
        return null;
      },
    };

    const storage = adaptForLocalStorage<PanelLayout, PanelLayout>({
      toSerializable: (v) => v,
      fromSerializable: (saved) => mergePanelLayout(saved),
      storage: mockStorage,
    });

    // This is what atomWithStorage calls on init
    const defaultValue: PanelLayout = {
      sidebar: [],
      developerPanel: [],
    };
    const result = storage.getItem("marimo:panel-layout", defaultValue);

    expect(result).toEqual({
      sidebar: [
        "files",
        "variables",
        "packages",
        "ai",
        "outline",
        "documentation",
        "dependencies",
      ],
      developerPanel: [
        "errors",
        "scratchpad",
        "tracing",
        "secrets",
        "snippets",
        "logs",
        "terminal",
      ],
    });
  });

  it("returns default when localStorage is empty", () => {
    const mockStorage: Storage = {
      length: 0,
      key: () => null,
      clear: () => undefined,
      removeItem: () => undefined,
      setItem: () => undefined,
      getItem: () => null,
    };

    const storage = adaptForLocalStorage<PanelLayout, PanelLayout>({
      toSerializable: (v) => v,
      fromSerializable: (saved) => mergePanelLayout(saved),
      storage: mockStorage,
    });

    const defaultValue: PanelLayout = {
      sidebar: ["files"],
      developerPanel: ["errors"],
    };
    const result = storage.getItem("marimo:panel-layout", defaultValue);

    // Should return the initialValue (default) since nothing in storage
    expect(result).toEqual(defaultValue);
  });
});
