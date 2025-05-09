/* Copyright 2024 Marimo. All rights reserved. */

import { Awareness, LoroDoc, LoroMap, LoroText } from "loro-crdt";
import type { CellId } from "@/core/cells/ids";
import { isWasm } from "@/core/wasm/utils";
import type { Extension } from "@codemirror/state";
import ReconnectingWebSocket from "partysocket/ws";
import { createWsUrl } from "@/core/websocket/createWsUrl";
import { getSessionId } from "@/core/kernel/session";
import { once } from "@/utils/once";
import { loroSyncAnnotation, loroSyncPlugin } from "./loro/sync";
import { EditorView, ViewPlugin } from "@codemirror/view";
import {
  getInitialLanguageAdapter,
  languageAdapterState,
  setLanguageAdapter,
  switchLanguage,
} from "../language/extension";
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
import { initialMode } from "@/core/mode";
import { isRtcEnabled, usernameAtom } from "@/core/rtc/state";
import { getColor } from "./loro/colors";
import {
  languageMetadataField,
  setLanguageMetadata,
  updateLanguageMetadata,
} from "../language/metadata";
import { invariant } from "@/utils/invariant";
import { isEqual } from "lodash-es";

const logger = Logger.get("rtc");
const awarenessLogger = logger.get("awareness").disabled();

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
  logger.debug("creating websocket");

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
      awarenessLogger.debug("applied awareness update");
      return;
    }

    // Handle doc update
    doc.import(data);
    logger.debug("imported doc change. new doc:", doc.toJSON());

    // Set the active doc only once the first message is received
    // This is to ensure the LoroDoc is created on the server, and not the client.
    if (store.get(connectedDocAtom) !== doc) {
      store.set(connectedDocAtom, doc);
    }
  });

  // Handle open event
  ws.addEventListener("open", () => {
    logger.debug("websocket open");
  });

  // Handle close event
  ws.addEventListener("close", (e) => {
    logger.warn("websocket close", e);

    // Remove the active doc
    if (store.get(connectedDocAtom) === doc) {
      store.set(connectedDocAtom, undefined);
    }
  });

  return ws;
});

// Kickoff the WS connection for edit mode
if (isRtcEnabled() && initialMode === "edit") {
  getWs();
}

// Send local updates to the server
doc.subscribeLocalUpdates((update) => {
  logger.debug("local update, sending to server");
  const ws = getWs();
  ws.send(update);
});

// Handle awareness changes
awareness.addListener((updates, origin) => {
  const changes = [...updates.added, ...updates.removed, ...updates.updated];
  if (origin === "local") {
    awarenessLogger.debug("awareness changes", changes);
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
    logger.log("initializing code for new cell", initialCode);
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
  const syncLanguage = (view: EditorView, language: LoroText) => {
    const currentLang = view.state.field(languageAdapterState).type;
    const newLang = language.toString() as LanguageAdapterType;
    if (!newLang) {
      return;
    }

    if (newLang !== currentLang) {
      logger.debug(
        `[incoming] setting language type: ${currentLang} -> ${newLang}`,
      );
      switchLanguage(view, newLang, { keepCodeAsIs: true });
    }
  };

  const syncLanguageMetadata = (
    view: EditorView,
    languageMetadata: LoroMap,
  ) => {
    const previousLanguageMetadata = view.state.field(languageMetadataField);
    const newLanguageMetadata = languageMetadata.toJSON();
    if (isEqual(previousLanguageMetadata, newLanguageMetadata)) {
      return;
    }

    view.dispatch({
      effects: [updateLanguageMetadata.of(newLanguageMetadata)],
      annotations: [loroSyncAnnotation.of(true)],
    });
  };

  return ViewPlugin.define((view) => {
    let unsubscribeDoc: () => void;

    // Initialize after a single tick
    Promise.resolve().then(() => {
      // Language type
      const langType = doc.getByPath(`languages/${cellId}`);
      if (!langType) {
        logger.error("no language container found for cell", cellId);
        return;
      }
      invariant(
        langType instanceof LoroText,
        "language type is not a LoroText",
      );

      // Language metadata
      const langMeta = doc.getByPath(`language_metadata/${cellId}`);
      if (!langMeta) {
        logger.error("no language metadata container found for cell", cellId);
        return;
      }
      invariant(
        langMeta instanceof LoroMap,
        "language metadata is not a LoroMap",
      );

      // Run once
      syncLanguage(view, langType);
      syncLanguageMetadata(view, langMeta);

      // Subscribe to language and metadata changes
      unsubscribeDoc = doc.subscribe((event) => {
        if (event.origin === "local") {
          // Skip if the change is local
          return;
        }

        const hasAnyLanguageTypeChanges = event.events.some(
          (e) => e.target === langType.id,
        );
        const hasAnyLanguageMetadataChanges = event.events.some(
          (e) => e.target === langMeta.id,
        );

        if (hasAnyLanguageTypeChanges) {
          syncLanguage(view, langType);
        }
        if (hasAnyLanguageMetadataChanges) {
          syncLanguageMetadata(view, langMeta);
        }
      });
    });

    return {
      destroy() {
        unsubscribeDoc();
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
  // Get or create the language type container
  const currentLang = doc
    .getMap("languages")
    .getOrCreateContainer(cellId, new LoroText());

  // Get or create the language metadata container
  const currentLanguageMetadata = doc
    .getMap("language_metadata")
    .getOrCreateContainer(cellId, new LoroMap());

  return EditorView.updateListener.of((update) => {
    const isInitialized = currentLang.toString() !== "";

    // Skip if the doc hasn't changed and the language is already set
    if (!update.docChanged && isInitialized) {
      return;
    }

    // If the language is not set, set it to the current language
    // and update the LoroDoc
    if (!isInitialized) {
      const lang = getInitialLanguageAdapter(update.state).type;
      switchLanguage(update.view, lang);
      logger.debug("no initial language, setting default to", lang);

      // Sync the language to the LoroDoc
      currentLang.delete(0, currentLang.length);
      currentLang.insert(0, lang);

      // Sync the language metadata to the LoroDoc
      logger.debug(
        "no initial language metadata, setting default to",
        update.state.field(languageMetadataField),
      );
      const metadata = update.state.field(languageMetadataField);
      for (const key of Object.keys(metadata)) {
        currentLanguageMetadata.set(key, metadata[key]);
      }

      // Commit the changes
      doc.commit();

      return;
    }

    let hasChanges = false;

    for (const tr of update.transactions) {
      const isSyncOperation = tr.annotation(loroSyncAnnotation);
      if (isSyncOperation) {
        continue;
      }

      for (const e of tr.effects) {
        // Language type
        if (
          e.is(setLanguageAdapter) &&
          currentLang.toString() !== e.value.type
        ) {
          logger.debug(
            `[outgoing] language change: ${currentLang} -> ${e.value.type}`,
          );
          currentLang.delete(0, currentLang.length);
          currentLang.insert(0, e.value.type);
          hasChanges = true;
        }

        // Language metadata
        if (e.is(updateLanguageMetadata) || e.is(setLanguageMetadata)) {
          const metadata = e.value;

          // If it is set, we should clear the metadata first
          if (e.is(setLanguageMetadata)) {
            logger.debug("[outgoing] setting language metadata: ", metadata);
            currentLanguageMetadata.clear();
          } else {
            logger.debug("[outgoing] updating language metadata: ", metadata);
          }

          for (const key of Object.keys(metadata)) {
            currentLanguageMetadata.set(key, metadata[key]);
          }
          hasChanges = true;
        }
      }
    }

    if (hasChanges) {
      doc.commit();
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
