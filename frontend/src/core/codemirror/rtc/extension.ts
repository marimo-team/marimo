/* Copyright 2024 Marimo. All rights reserved. */
import { yCollab } from "y-codemirror.next";
import type { CellId } from "@/core/cells/ids";
import { isWasm } from "@/core/wasm/utils";
import type { Extension } from "@codemirror/state";
import { CellProviderManager } from "./cell-manager";
import { EditorView, ViewPlugin } from "@codemirror/view";
import {
  languageAdapterState,
  setLanguageAdapter,
  switchLanguage,
} from "../language/extension";
import { LanguageAdapters } from "../language/LanguageAdapters";
import type { LanguageAdapterType } from "../language/types";
import { Logger } from "@/utils/Logger";

export function realTimeCollaboration(
  cellId: CellId,
  initialCode = "",
): { extension: Extension; code: string } {
  if (isWasm()) {
    return {
      extension: [],
      code: initialCode,
    };
  }

  const manager = CellProviderManager.getInstance();
  const { ytext, ylanguage } = manager.getOrCreateProvider(cellId, initialCode);

  // Create a view plugin to observe language changes
  const languageObserver = ViewPlugin.define((view) => {
    const observer = () => {
      const newLang = ylanguage.toJSON() as LanguageAdapterType;
      const currentLang = view.state.field(languageAdapterState).type;
      if (newLang !== currentLang) {
        Logger.debug(
          `[debug] Received language change: ${currentLang} -> ${newLang}`,
        );
        const adapter = LanguageAdapters[newLang]();
        switchLanguage(view, adapter.type, { keepCodeAsIs: true });
      }
    };

    ylanguage.observe(observer);
    return {
      destroy() {
        ylanguage.unobserve(observer);
      },
    };
  });

  // Listen for language changes
  const languageListener = EditorView.updateListener.of((update) => {
    for (const tr of update.transactions) {
      for (const e of tr.effects) {
        if (e.is(setLanguageAdapter)) {
          const currentLang = ylanguage.toJSON();
          if (currentLang !== e.value.type) {
            Logger.debug(
              `[debug] Setting language: ${currentLang} -> ${e.value.type}`,
            );
            ylanguage.doc?.transact(() => {
              ylanguage.delete(0, ylanguage.length);
              ylanguage.insert(0, e.value.type);
            });
          }
        }
      }
    }
  });

  const extension = [languageObserver, languageListener, yCollab(ytext, null)];

  return {
    code: ytext.toJSON(),
    extension,
  };
}
