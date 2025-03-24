/* Copyright 2024 Marimo. All rights reserved. */
import { WebsocketProvider } from "y-websocket";
import * as Y from "yjs";
import type { CellId } from "@/core/cells/ids";
import { KnownQueryParams } from "@/core/constants";
import { getSessionId } from "@/core/kernel/session";
import { connectionAtom } from "@/core/network/connection";
import { WebSocketState } from "@/core/websocket/types";
import { store } from "@/core/state/jotai";
import { Logger } from "@/utils/Logger";

const DOC_KEY = "code";
const LANGUAGE_KEY = "language";

export class CellProviderManager {
  private providers = new Map<CellId, WebsocketProvider>();
  private static instance: CellProviderManager;

  private constructor() {
    this.listenForConnectionChanges();
  }

  static getInstance(): CellProviderManager {
    if (!CellProviderManager.instance) {
      CellProviderManager.instance = new CellProviderManager();
    }
    return CellProviderManager.instance;
  }

  getOrCreateProvider(
    cellId: CellId,
    initialCode = "",
  ): { provider: WebsocketProvider; ytext: Y.Text; ylanguage: Y.Text } {
    const existingProvider = this.providers.get(cellId);
    if (existingProvider) {
      return {
        provider: existingProvider,
        ytext: existingProvider.doc.getText(DOC_KEY),
        ylanguage: existingProvider.doc.getText(LANGUAGE_KEY),
      };
    }

    const ydoc = new Y.Doc();
    const ytext = ydoc.getText(DOC_KEY);
    const ylanguage = ydoc.getText(LANGUAGE_KEY);

    const params: Record<string, string> = {
      session_id: getSessionId(),
    };
    const searchParams = new URLSearchParams(window.location.search);
    const filePath = searchParams.get(KnownQueryParams.filePath);
    if (filePath) {
      params.file = filePath;
    }

    const provider = new WebsocketProvider("ws", cellId, ydoc, {
      params,
      // This serves as a heartbeat to keep the connection alive
      // otherwise, the connection will close and can lead to data loss
      // or duplicate code from an awkward rsync.
      resyncInterval: 5000,
    });

    this.providers.set(cellId, provider);
    provider.on("connection-close", () => {
      Logger.warn("RTC: connection closed. This could lead to data loss.");
    });
    provider.on("connection-error", () => {
      Logger.warn("RTC: connection error. This could lead to data loss.");
    });

    return { provider, ytext, ylanguage };
  }

  listenForConnectionChanges(): void {
    const handleDisconnect = () => {
      const value = store.get(connectionAtom);
      const shouldDisconnect =
        value.state === WebSocketState.CLOSED ||
        value.state === WebSocketState.CLOSING;
      if (shouldDisconnect) {
        this.disconnectAll();
      }
    };
    store.sub(connectionAtom, handleDisconnect);
  }

  disconnect(cellId: CellId): void {
    const provider = this.providers.get(cellId);
    if (provider) {
      provider.destroy();
      this.providers.delete(cellId);
    }
  }

  disconnectAll(): void {
    for (const [cellId] of this.providers) {
      this.disconnect(cellId);
    }
  }
}
