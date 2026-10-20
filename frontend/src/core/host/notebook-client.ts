/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import { type Atom, atom, type createStore } from "jotai/vanilla";
import {
  type ConnectionStatus,
  ConnectionState,
  ConnectionClosedReason,
  type CloseDecision,
  type NotebookTransport,
  TransportReadyState,
} from "./connection";
import { parseNotebookEvent } from "./events";

/** A connection to a notebook on a marimo host. */
export interface NotebookClient {
  /** Transport state, independent of kernel readiness. */
  readonly connectionAtom: Atom<ConnectionStatus>;
  /** Attempt to restore a closed connection after checking host health. */
  reconnect(): Promise<void>;
}

/** The transport and application callbacks needed to connect a notebook. */
export interface NotebookConnection {
  /** Create a transport that reads the URL again on each connection attempt. */
  createTransport: (url: () => string) => NotebookTransport;
  /** The current stream URL, including authentication and subscription options. */
  url: () => string;
  /** Host events require an intact stream; legacy notifications are independent. */
  messageFormat: "host" | "session";
  /** Abort to close the transport and clear the client's state. */
  signal: AbortSignal;
  /** Wait until the host can accept the initial connection. */
  waitUntilReady: () => Promise<void>;
  /** Check whether the host is reachable before an explicit reconnect. */
  checkHealth: () => Promise<boolean>;
  /** Decode wire text without interpreting its event type. */
  decodeJson: (message: string) => unknown;
  /** Handle a native marimo notification. Its payload has not been validated. */
  onNotification: (notification: unknown) => void;
  /** Report a malformed message without coupling the client to editor UI. */
  onMessageError: (error: unknown) => void;
  /** Choose the connection status and retry policy after the transport closes. */
  classifyClose: (event: CloseEvent) => CloseDecision;
}

/** Create a client without opening a connection. */
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
    messageFormat,
    signal,
    waitUntilReady,
    checkHealth,
    onNotification,
    onMessageError,
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
        if (messageFormat === "session") {
          onMessageError(error);
          return;
        }
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
        transport.readyState === TransportReadyState.OPEN ||
        transport.readyState === TransportReadyState.CONNECTING
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

    if (transport.readyState === TransportReadyState.CLOSED) {
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
