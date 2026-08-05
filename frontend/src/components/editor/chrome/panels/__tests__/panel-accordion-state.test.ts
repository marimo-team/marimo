/* Copyright 2026 Marimo. All rights reserved. */

import { afterAll, expect, it } from "vitest";
import { store } from "@/core/state/jotai";
import { availableStorage } from "@/utils/storage/storage";

const SESSION_PANEL_KEY = "marimo:session-panel:state";
const FILE_EXPLORER_PANEL_KEY = "marimo:file-explorer-panel:state";

afterAll(() => {
  availableStorage.removeItem(SESSION_PANEL_KEY);
  availableStorage.removeItem(FILE_EXPLORER_PANEL_KEY);
});

it("preserves stored panel state when expanding an unmounted panel", async () => {
  const persistedState = {
    openSections: [],
    hasUserInteracted: true,
  };
  availableStorage.setItem(SESSION_PANEL_KEY, JSON.stringify(persistedState));
  availableStorage.setItem(
    FILE_EXPLORER_PANEL_KEY,
    JSON.stringify(persistedState),
  );

  // Import after seeding storage to exercise atom initialization before a
  // lazily mounted panel subscribes to it.
  const { expandAccordionSection, fileExplorerPanelAtom, sessionPanelAtom } =
    await import("../panel-accordion-state");

  expandAccordionSection(sessionPanelAtom, "datasources");
  expandAccordionSection(fileExplorerPanelAtom, "remote-storage");

  expect(store.get(sessionPanelAtom)).toEqual({
    openSections: ["datasources"],
    hasUserInteracted: true,
  });
  expect(store.get(fileExplorerPanelAtom)).toEqual({
    openSections: ["remote-storage"],
    hasUserInteracted: true,
  });
});
