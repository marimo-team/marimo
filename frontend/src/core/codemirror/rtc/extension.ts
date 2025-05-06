/* Copyright 2024 Marimo. All rights reserved. */

import { Awareness, LoroDoc, LoroText } from "loro-crdt";
import type { CellId } from "@/core/cells/ids";
import { isWasm } from "@/core/wasm/utils";
import type { Extension } from "@codemirror/state";
import ReconnectingWebSocket from "partysocket/ws";
import { createWsUrl } from "@/core/websocket/createWsUrl";
import { getSessionId } from "@/core/kernel/session";
import { once } from "@/utils/once";
import { LoroSyncPlugin } from "./loro/sync";
import { EditorView, ViewPlugin } from "@codemirror/view";
import {
  languageAdapterState,
  setLanguageAdapter,
  switchLanguage,
} from "../language/extension";
import { LanguageAdapters } from "../language/LanguageAdapters";
import type { LanguageAdapterType } from "../language/types";
import { rtcLogger } from "./utils";
import { cellIdState } from "../config/extension";
import { invariant } from "@/utils/invariant";

// Create a Loro document
const doc = new LoroDoc();
const awareness: Awareness = new Awareness(doc.peerIdStr);
// const undoManager = new UndoManager(doc, {});

const log = rtcLogger;

// Create a websocket connection to the server
const getWs = once(() => {
  log("creating websocket");
  const url = createWsUrl(getSessionId()).replace("/ws", "/ws_sync");
  const ws = new ReconnectingWebSocket(url, undefined, {
    // We don't want Infinity retries
    maxRetries: 10,
    debug: false,
    connectionTimeout: 10_000,
  });

  // Receive updates from the server
  ws.addEventListener("message", async (event) => {
    const blob: Blob = event.data;
    const bytes = await blob.arrayBuffer();
    doc.import(new Uint8Array(bytes));
    log("imported doc change. new doc:", doc.toJSON());
  });

  // Handle open event
  ws.addEventListener("open", () => {
    log("websocket open");
  });

  // Handle close event
  ws.addEventListener("close", () => {
    log("websocket close");
  });

  return ws;
});

// Send local updates to the server
doc.subscribeLocalUpdates((update) => {
  log("local update", update);
  const ws = getWs();
  ws.send(update);
});

// Handle awareness changes
awareness.addListener((updates, origin) => {
  const changes = [...updates.added, ...updates.removed, ...updates.updated];
  if (origin === "local") {
    log("awareness changes", changes);
    const ws = getWs();
    ws.send(awareness.encode(changes));
  }
});

export function realTimeCollaboration(
  cellId: CellId,
  _updateCellCode: (code: string) => void,
  initialCode = "",
): { extension: Extension; code?: string } {
  if (isWasm()) {
    return {
      extension: [],
      code: initialCode,
    };
  }

  // Connect if not already connected
  const ws = getWs();
  if (ws.shouldReconnect) {
    log("connecting to websocket");
    ws.reconnect();
  }

  return {
    extension: [
      languageObserverExtension(),
      languageListenerExtension(),
      LoroSyncPlugin(doc, ["codes", cellId], () =>
        doc.getMap("codes").getOrCreateContainer(cellId, new LoroText()),
      ),
    ],
  };
}

/**
 * Create a view plugin to observe language changes
 * When the language changes, we need to update our local language
 * Server -> Local
 * @param cellId - The cell id
 * @returns Extension
 */
export function languageObserverExtension() {
  return ViewPlugin.define((view) => {
    const cellId = view.state.facet(cellIdState);
    invariant(cellId !== undefined, "cellId is undefined");

    const unsubscribeLanguage = doc.subscribe(() => {
      const language = doc.getByPath(`languages/${cellId}`) as LoroText;
      if (!language) {
        return;
      }
      const newLang = language.toString() as LanguageAdapterType;
      const currentLang = view.state.field(languageAdapterState).type;

      if (newLang !== currentLang) {
        log(`[debug] Received language change: ${currentLang} -> ${newLang}`);
        const adapter = LanguageAdapters[newLang]();
        switchLanguage(view, adapter.type);
      }
    });

    return {
      destroy() {
        unsubscribeLanguage();
      },
    };
  });
}

/**
 * Listen for local language changes
 * This is used to sync the language with the server
 * Local -> Server
 * @returns Extension
 */
function languageListenerExtension() {
  return EditorView.updateListener.of((update) => {
    const cellId = update.state.facet(cellIdState);
    invariant(cellId !== undefined, "cellId is undefined");

    const currentLang = doc
      .getMap("languages")
      .getOrCreateContainer(cellId, new LoroText());

    if (!currentLang.toString()) {
      // If the language is not set, set it to the current language
      log("no language", update);
      const lang = update.state.field(languageAdapterState).type;
      currentLang.insert(0, lang);
      doc.commit();
      return;
    }

    for (const tr of update.transactions) {
      for (const e of tr.effects) {
        if (
          e.is(setLanguageAdapter) &&
          currentLang.toString() !== e.value.type
        ) {
          log(`[debug] Setting language: ${currentLang} -> ${e.value.type}`);
          currentLang.delete(0, currentLang.length);
          currentLang.insert(0, e.value.type);
          doc.commit();
        }
      }
    }
  });
}
