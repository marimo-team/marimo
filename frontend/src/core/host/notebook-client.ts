/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { type Atom, atom, type createStore } from "jotai/vanilla";
import {
  type ConnectionStatus,
  ConnectionState,
  ConnectionClosedReason,
  type CloseDecision,
  type NotebookTransport,
} from "./connection";
import { parseNotebookEvent } from "./events";
import type * as Protocol from "./protocol";

/** A client's view of a notebook on a marimo host. */
export interface NotebookClient {
  /** Transport connectivity; an open connection does not imply session readiness. */
  readonly connectionAtom: Atom<ConnectionStatus>;
  /** Attempt to restore a closed connection after checking host health. */
  reconnect(): Promise<void>;
}

/** The adapter that connects a notebook to its environment. */
export interface NotebookConnection {
  createTransport: (url: () => string) => NotebookTransport;
  url: () => string;
  signal: AbortSignal;
  waitUntilReady: () => Promise<void>;
  checkHealth: () => Promise<boolean>;
  /** Decode wire text. The client validates the resulting value. */
  decodeJson: (message: string) => unknown;
  /** Handle the inner native marimo notification. */
  onNotification: (
    notification: Protocol.MarimoEvent["data"]["marimo"],
  ) => void;
  classifyClose: (event: CloseEvent) => CloseDecision;
}

// Standard WebSocket ready states, shared by the transport adapters.
const CONNECTING = 0;
const OPEN = 1;
const CLOSED = 3;

/** Creates inert state. Only the owning hook connects it to a transport. */
export function createNotebookClient(store: ReturnType<typeof createStore>) {
  const connectionAtom = atom<ConnectionStatus>({
    state: ConnectionState.NOT_STARTED,
  });
  let reconnect: (() => Promise<void>) | undefined;
  const client: NotebookClient = {
    connectionAtom,
    reconnect: async () => reconnect?.(),
  };

  function connect({
    createTransport,
    url,
    signal,
    waitUntilReady,
    checkHealth,
    onNotification,
    decodeJson,
    classifyClose,
  }: NotebookConnection) {
    if (signal.aborted) {
      return;
    }
    let shouldRetry = true;
    let terminal = false;
    let checkingHealth = false;
    const transport = createTransport(url);
    const setStatus = (status: ConnectionStatus) =>
      store.set(connectionAtom, status);
    const disconnected = {
      state: ConnectionState.CLOSED,
      code: ConnectionClosedReason.KERNEL_DISCONNECTED,
      reason: "kernel not found",
    } satisfies ConnectionStatus;

    function retry(code?: number, reason?: string) {
      if (!signal.aborted && !terminal && shouldRetry) {
        shouldRetry = false;
        transport.reconnect(code, reason);
      }
    }

    function onOpen() {
      if (signal.aborted || terminal) {
        return;
      }
      shouldRetry = true;
      setStatus({ state: ConnectionState.OPEN });
    }

    function onClose(event: CloseEvent) {
      if (signal.aborted || terminal) {
        return;
      }
      Logger.warn("Notebook connection closed", event.code, event.reason);
      const decision = classifyClose(event);
      setStatus(decision.status);
      if (decision.kind === "terminal") {
        terminal = true;
        transport.close();
      } else if (decision.kind === "retry") {
        retry(event.code, event.reason);
      } else {
        terminal = true;
      }
    }

    function onError(event: Event) {
      if (signal.aborted || terminal) {
        return;
      }
      Logger.warn("Notebook connection error", event);
      setStatus(disconnected);
      retry();
    }

    function onMessage(message: MessageEvent<string>) {
      if (signal.aborted || terminal) {
        return;
      }
      let event;
      try {
        event = parseNotebookEvent(decodeJson(message.data));
      } catch (error) {
        Logger.error("Failed to decode notebook message", error);
        terminal = true;
        setStatus({
          ...disconnected,
          reason: "Failed to decode notebook message",
        });
        transport.close();
        return;
      }
      if (event.event === "marimo") {
        onNotification(event.data.marimo);
      }
    }

    reconnect = async () => {
      if (
        signal.aborted ||
        checkingHealth ||
        transport.readyState === OPEN ||
        transport.readyState === CONNECTING
      ) {
        return;
      }
      checkingHealth = true;
      setStatus({ state: ConnectionState.CONNECTING });
      try {
        const healthy = await checkHealth();
        if (signal.aborted) {
          return;
        }
        if (!healthy) {
          shouldRetry = false;
          setStatus(disconnected);
          return;
        }
        terminal = false;
        shouldRetry = true;
        transport.reconnect();
      } catch (error) {
        if (!signal.aborted) {
          Logger.error("Notebook health check failed", error);
          shouldRetry = false;
          setStatus(disconnected);
        }
      } finally {
        checkingHealth = false;
      }
    };

    signal.addEventListener(
      "abort",
      () => {
        transport.removeEventListener("open", onOpen);
        transport.removeEventListener("close", onClose);
        transport.removeEventListener("error", onError);
        transport.removeEventListener("message", onMessage);
        transport.close();
        reconnect = undefined;
        setStatus({ state: ConnectionState.NOT_STARTED });
      },
      { once: true },
    );

    transport.addEventListener("open", onOpen);
    transport.addEventListener("close", onClose);
    transport.addEventListener("error", onError);
    transport.addEventListener("message", onMessage);

    if (transport.readyState === CLOSED) {
      setStatus({ state: ConnectionState.CONNECTING });
      void waitUntilReady()
        .then(() => {
          if (!signal.aborted) {
            transport.reconnect();
          }
        })
        .catch((error) => {
          if (!signal.aborted) {
            Logger.error("Healthy connection never made", error);
            terminal = true;
            setStatus(disconnected);
            transport.close();
          }
        });
    }
  }

  return { client, connect };
}
