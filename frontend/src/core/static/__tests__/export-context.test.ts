/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom

import type { ExtractAtomValue } from "jotai";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { hasRunAnyCellAtom } from "@/components/editor/cell/useRunCells";
import { userConfigAtom } from "@/core/config/config";
import { parseUserConfig } from "@/core/config/config-schema";
import { initialModeAtom } from "@/core/mode";
import { store } from "@/core/state/jotai";
import {
  getMarimoExportContext,
  hasTrustedExportContext,
  hasTrustedNotebookContext,
} from "../export-context";

type ExportContextWindow = Window & {
  __MARIMO_EXPORT_CONTEXT__?: {
    trusted: boolean;
    notebookCode?: string;
  };
};

function setAutoInstantiate(value: boolean) {
  const cleared = parseUserConfig({});
  store.set(userConfigAtom, {
    ...cleared,
    runtime: { ...cleared.runtime, auto_instantiate: value },
  });
}

describe("hasTrustedNotebookContext", () => {
  let previousHasRunAnyCell: ExtractAtomValue<typeof hasRunAnyCellAtom>;
  let previousConfig: ExtractAtomValue<typeof userConfigAtom>;
  let previousMode: ExtractAtomValue<typeof initialModeAtom>;
  let w: ExportContextWindow;

  beforeEach(() => {
    w = window as ExportContextWindow;
    previousHasRunAnyCell = store.get(hasRunAnyCellAtom);
    previousConfig = store.get(userConfigAtom);
    previousMode = store.get(initialModeAtom);
    store.set(hasRunAnyCellAtom, false);
    setAutoInstantiate(false);
    store.set(initialModeAtom, "edit");
    delete w.__MARIMO_EXPORT_CONTEXT__;
  });

  afterEach(() => {
    store.set(hasRunAnyCellAtom, previousHasRunAnyCell);
    store.set(userConfigAtom, previousConfig);
    store.set(initialModeAtom, previousMode);
    delete w.__MARIMO_EXPORT_CONTEXT__;
  });

  it("returns false in untrusted edit mode before interaction", () => {
    expect(hasTrustedNotebookContext()).toBe(false);
  });

  it("returns true once the user has run a cell", () => {
    store.set(hasRunAnyCellAtom, true);
    expect(hasTrustedNotebookContext()).toBe(true);
  });

  it("returns true when a trusted export context is installed", () => {
    w.__MARIMO_EXPORT_CONTEXT__ = { trusted: true };
    expect(hasTrustedNotebookContext()).toBe(true);
  });

  it("returns true when auto_instantiate is enabled", () => {
    setAutoInstantiate(true);
    expect(hasTrustedNotebookContext()).toBe(true);
  });

  it("returns true in read mode", () => {
    store.set(initialModeAtom, "read");
    expect(hasTrustedNotebookContext()).toBe(true);
  });

  it("returns false if initialMode throws (config not yet applied)", () => {
    store.set(initialModeAtom, undefined);
    expect(hasTrustedNotebookContext()).toBe(false);
  });
});

describe("hasTrustedExportContext / getMarimoExportContext shape validation", () => {
  let w: ExportContextWindow;

  beforeEach(() => {
    w = window as ExportContextWindow;
    delete w.__MARIMO_EXPORT_CONTEXT__;
  });

  afterEach(() => {
    delete w.__MARIMO_EXPORT_CONTEXT__;
  });

  it("accepts a valid context", () => {
    w.__MARIMO_EXPORT_CONTEXT__ = { trusted: true, notebookCode: "x = 1" };
    expect(hasTrustedExportContext()).toBe(true);
    expect(getMarimoExportContext()).toEqual({
      trusted: true,
      notebookCode: "x = 1",
    });
  });

  it("rejects a context where `trusted` is not exactly true", () => {
    w.__MARIMO_EXPORT_CONTEXT__ = {
      trusted: "yes" as unknown as true,
    };
    expect(hasTrustedExportContext()).toBe(false);
    expect(getMarimoExportContext()).toBeUndefined();
  });

  it("rejects a context with non-string notebookCode", () => {
    w.__MARIMO_EXPORT_CONTEXT__ = {
      trusted: true,
      notebookCode: 42 as unknown as string,
    };
    expect(getMarimoExportContext()).toBeUndefined();
  });
});
