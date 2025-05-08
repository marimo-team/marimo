/* Copyright 2024 Marimo. All rights reserved. */

import { Awareness, LoroDoc, LoroText } from "loro-crdt";
import type { CellId } from "@/core/cells/ids";
import { isWasm } from "@/core/wasm/utils";
import type { Extension } from "@codemirror/state";
import ReconnectingWebSocket from "partysocket/ws";
import { createWsUrl } from "@/core/websocket/createWsUrl";
import { getSessionId } from "@/core/kernel/session";
import { once } from "@/utils/once";
import { loroSyncPlugin } from "./loro/sync";
import { EditorView, ViewPlugin } from "@codemirror/view";
import {
  getInitialLanguageAdapter,
  languageAdapterState,
  setLanguageAdapter,
  switchLanguage,
} from "../language/extension";
import { LanguageAdapters } from "../language/LanguageAdapters";
import type { LanguageAdapterType } from "../language/types";
import { atom } from "jotai";
import { waitForConnectionOpen } from "@/core/network/connection";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";
import { loroCursorTheme, RemoteAwarenessPlugin } from "./loro/awareness";
import type { AwarenessState, ScopeId, Uid } from "./loro/awareness";
import { AwarenessPlugin } from "./loro/awareness";
import { createSelectionLayer } from "./loro/awareness";
import { createCursorLayer } from "./loro/awareness";
import { remoteAwarenessStateField } from "./loro/awareness";
import type { UserState } from "./loro/awareness";
import { getFeatureFlag } from "@/core/config/feature-flag";
import { initialMode } from "@/core/mode";
import { usernameAtom } from "@/core/rtc/state";
import { getColor } from "./loro/colors";

const AWARENESS_PREFIX = "awareness:";

// Utility functions for message handling
function prefixMessage(token: string, message: Uint8Array): Uint8Array {
  const tokenBytes = new TextEncoder().encode(token);
  return new Uint8Array([...tokenBytes, ...message]);
}

function hasPrefix(data: Uint8Array, prefix: string): boolean {
  const decoder = new TextDecoder();
  const dataPrefix = decoder.decode(data.slice(0, prefix.length));
  return dataPrefix === prefix;
}

function removePrefix(data: Uint8Array, prefix: string): Uint8Array {
  return data.slice(prefix.length);
}

export const connectedDocAtom = atom<LoroDoc | "disabled" | undefined>(
  undefined,
);

// Create a Loro document
const doc = new LoroDoc();
const awareness = new Awareness<AwarenessState>(doc.peerIdStr);
// const undoManager = new UndoManager(doc, {});

// Create a websocket connection to the server
const getWs = once(() => {
  Logger.debug("[rtc] creating websocket");

  const url = createWsUrl(getSessionId()).replace("/ws", "/ws_sync");

  // Create the websocket, but don't connect it yet
  const ws = new ReconnectingWebSocket(url, undefined, {
    // We don't want Infinity retries
    maxRetries: 10,
    debug: false,
    startClosed: true,
    connectionTimeout: 10_000,
  });

  // Start the connection
  Promise.resolve().then(async () => {
    // First wait the main /ws connection to be open
    // This is to ensure the LoroDoc is created on the server
    await waitForConnectionOpen();

    // Now open the websocket
    ws.reconnect();
  });

  // Receive updates from the server
  ws.addEventListener("message", async (event) => {
    const blob: Blob = event.data;
    const bytes = await blob.arrayBuffer();
    const data = new Uint8Array(bytes);

    // Handle awareness update
    if (hasPrefix(data, AWARENESS_PREFIX)) {
      const awarenessData = removePrefix(data, AWARENESS_PREFIX);
      awareness.apply(awarenessData);
      Logger.debug("[rtc] applied awareness update");
      return;
    }

    // Handle doc update
    doc.import(data);
    Logger.debug("[rtc] imported doc change. new doc:", doc.toJSON());

    // Set the active doc only once the first message is received
    // This is to ensure the LoroDoc is created on the server, and not the client.
    if (store.get(connectedDocAtom) !== doc) {
      store.set(connectedDocAtom, doc);
    }
  });

  // Handle open event
  ws.addEventListener("open", () => {
    Logger.debug("[rtc] websocket open");
  });

  // Handle close event
  ws.addEventListener("close", (e) => {
    Logger.warn("[rtc] websocket close", e);

    // Remove the active doc
    if (store.get(connectedDocAtom) === doc) {
      store.set(connectedDocAtom, undefined);
    }
  });

  return ws;
});

// Kick off the connection for edit mode
if (getFeatureFlag("rtc_v2") && initialMode === "edit") {
  getWs();
}

// Send local updates to the server
doc.subscribeLocalUpdates((update) => {
  Logger.debug("[rtc] local update, sending to server");
  const ws = getWs();
  ws.send(update);
});

// Handle awareness changes
awareness.addListener((updates, origin) => {
  const changes = [...updates.added, ...updates.removed, ...updates.updated];
  if (origin === "local") {
    Logger.debug("[rtc] awareness changes", changes);
    const ws = getWs();
    ws.send(prefixMessage(AWARENESS_PREFIX, awareness.encode(changes)));
  }
});

export function realTimeCollaboration(
  cellId: CellId,
  _updateCellCode: (code: string) => void,
  initialCode = "",
): { extension: Extension; code: string } {
  if (isWasm()) {
    return {
      extension: [],
      code: initialCode,
    };
  }

  // Get or create the code container
  const hasPath = doc.getByPath(`codes/${cellId}`) !== undefined;
  const loroText = doc
    .getMap("codes")
    .getOrCreateContainer(cellId, new LoroText());
  if (!hasPath) {
    Logger.warn("[rtc] initializing code for new cell", initialCode);
    loroText.insert(0, initialCode);
  }

  const userName = store.get(usernameAtom) || "Anonymous";
  return {
    code: initialCode.toString(),
    extension: [
      languageObserverExtension(cellId),
      languageListenerExtension(cellId),
      loroAwarenessPlugin(
        doc,
        awareness,
        {
          name: userName,
          colorClassName: getColor(userName),
        },
        () => loroText,
        cellId,
      ),
      loroSyncPlugin(doc, ["codes", cellId], () => {
        return loroText;
      }),
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
function languageObserverExtension(cellId: CellId) {
  const updateLanguage = (view: EditorView) => {
    const language = doc.getByPath(`languages/${cellId}`) as
      | LoroText
      | undefined;
    if (!language) {
      return;
    }
    const currentLang = view.state.field(languageAdapterState).type;
    const newLang = language.toString() as LanguageAdapterType;

    if (newLang !== currentLang) {
      Logger.debug(
        `[rtc] Received language change: ${currentLang} -> ${newLang}`,
      );
      const adapter = LanguageAdapters[newLang];
      switchLanguage(view, adapter.type, { keepCodeAsIs: true });
    }
  };

  return ViewPlugin.define((view) => {
    // Initialize the language
    Promise.resolve().then(() => updateLanguage(view));

    const unsubscribeLanguage = doc.subscribe(() => {
      updateLanguage(view);
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
function languageListenerExtension(cellId: CellId) {
  return EditorView.updateListener.of((update) => {
    const currentLang = doc
      .getMap("languages")
      .getOrCreateContainer(cellId, new LoroText());

    if (!currentLang.toString()) {
      // If the language is not set, set it to the current language
      const lang = getInitialLanguageAdapter(update.state).type;
      switchLanguage(update.view, lang);
      Logger.debug("[rtc] no language, setting default to", lang);
      currentLang.delete(0, currentLang.length);
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
          Logger.debug(
            `[rtc] Setting language: ${currentLang} -> ${e.value.type}`,
          );
          currentLang.delete(0, currentLang.length);
          currentLang.insert(0, e.value.type);
          doc.commit();
        }
      }
    }
  });
}

/**
 * Create a plugin to observe awareness changes
 */
function loroAwarenessPlugin(
  doc: LoroDoc,
  awareness: Awareness<AwarenessState>,
  user: UserState,
  getTextFromDoc: (doc: LoroDoc) => LoroText,
  cellId: CellId,
  getUserId?: () => Uid,
): Extension[] {
  const scopeId = `loro:cell:${cellId}` as ScopeId;

  return [
    remoteAwarenessStateField,
    createCursorLayer(),
    createSelectionLayer(),
    ViewPlugin.define(
      (view) =>
        new AwarenessPlugin(
          view,
          doc,
          user,
          awareness,
          getTextFromDoc,
          scopeId,
          getUserId,
        ),
    ),
    ViewPlugin.define(
      (view) => new RemoteAwarenessPlugin(view, doc, awareness, scopeId),
    ),
    loroCursorTheme,
  ];
}
