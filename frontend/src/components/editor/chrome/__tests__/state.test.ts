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
    const result = mergePanelLayout(saved);
    expect(result.developerPanel).toContain("terminal");
    // Existing user ordering is preserved at the front
    expect(result.developerPanel.slice(0, 6)).toEqual(saved.developerPanel);
    expect(result.sidebar).toEqual(saved.sidebar);
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
    const result = mergePanelLayout(saved);
    expect(result.sidebar[0]).toBe("files");
    expect(result.sidebar[1]).toBe("variables");
    expect(result.sidebar).toContain("packages");
    expect(result.sidebar).toContain("ai");
    expect(result.sidebar).toContain("outline");
    expect(result.sidebar).toContain("documentation");
    expect(result.sidebar).toContain("dependencies");
    expect(result.developerPanel).toEqual(saved.developerPanel);
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
    const result = mergePanelLayout(saved);
    expect(result.sidebar).toEqual(saved.sidebar);
    expect(result.developerPanel).toContain("terminal");
    expect(result.developerPanel).toContain("snippets");
    expect(result.developerPanel.indexOf("errors")).toBe(0);
    expect(result.developerPanel.indexOf("scratchpad")).toBe(1);
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
    const result = mergePanelLayout(saved);
    expect(result.sidebar).toEqual(saved.sidebar);
    expect(result.developerPanel).toEqual(saved.developerPanel);
  });

  it("preserves panels the user moved between sections", () => {
    const saved: PanelLayout = {
      sidebar: ["files"],
      developerPanel: ["errors", "variables"],
    };
    const result = mergePanelLayout(saved);
    expect(result.sidebar).not.toContain("variables");
    expect(result.developerPanel).toContain("variables");
  });

  it("handles empty saved layout", () => {
    const saved: PanelLayout = {
      sidebar: [],
      developerPanel: [],
    };
    const result = mergePanelLayout(saved);
    expect(result.sidebar.length).toBeGreaterThan(0);
    expect(result.developerPanel.length).toBeGreaterThan(0);
    expect(result.sidebar).toContain("files");
    expect(result.developerPanel).toContain("errors");
    expect(result.developerPanel).toContain("terminal");
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

    // Terminal should now be present despite being absent from storage
    expect(result.developerPanel).toContain("terminal");
    // User's existing order is preserved
    expect(result.developerPanel.slice(0, 6)).toEqual(
      staleLayout.developerPanel,
    );
    expect(result.sidebar).toEqual(staleLayout.sidebar);
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
