/* Copyright 2026 Marimo. All rights reserved. */

import { Logger } from "@/utils/Logger";
import type { Attachment, NotebookOutput } from "@marimo-team/client/protocol";
import { createReducer } from "@marimo-team/client/reducer";
import { type Atom, atom, type createStore } from "jotai/vanilla";
import {
  type ConnectionStatus,
  ConnectionState,
  ConnectionClosedReason,
  type CloseDecision,
  type NotebookTransport,
  TransportReadyState,
} from "./connection";
import { type NotebookEvent, parseNotebookEvent } from "./events";
import { attachments } from "./resources/attachments";
import { type Document, document } from "./resources/document";

/** Events that may arrive without a cursor after `ready`. */
const UNCURSORED = new Set<NotebookEvent["event"]>([
  "reset",
  "marimo",
  "unknown",
]);

/** A connection to a notebook on a marimo host. */
export interface NotebookClient {
  /** Client connection status, independent of application session readiness. */
  readonly connectionAtom: Atom<ConnectionStatus>;
  /** Identity and capabilities, available while the stream is connected and ready. */
  readonly notebookAtom: Atom<NotebookOutput | null>;
  /**
   * The most recently confirmed document.
   *
   * Null until a snapshot is complete, after reset or removal, and on
   * connections without host document events. A temporary disconnection
   * retains the last document. Partial updates are not exposed.
   */
  readonly documentAtom: Atom<Document | null>;
  /** Live attachments, empty until the stream is ready or while disconnected. */
  readonly attachmentsAtom: Atom<readonly Attachment[]>;
  /** Attempt to restore a closed connection after checking host health. */
  reconnect(): Promise<void>;
}

/** The transport and application callbacks needed to connect a notebook. */
export interface NotebookConnection {
  /** Create a transport that reads the URL again on each connection attempt. */
  createTransport: (url: () => string) => NotebookTransport;
  /** The current stream URL, including authentication and subscription options. */
  url: () => string;
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
  /** Choose the connection status and retry policy after the transport closes. */
  classifyClose: (event: CloseEvent) => CloseDecision;
}

/** Create a client without opening a connection. */
export function createNotebookClient(store: ReturnType<typeof createStore>) {
  const connectionAtom = atom<ConnectionStatus>({
    state: ConnectionState.NOT_STARTED,
  });
  // One atom holds the whole stream, which resource atoms derive from.
  const reducer = createReducer({ document, attachments });
  const streamAtom = atom(reducer.initial);
  // A resumed stream is live, but presence waits for this connection's ready.
  const readyAtom = atom(false);
  const notebookAtom = atom((get) =>
    get(readyAtom) && get(connectionAtom).state === ConnectionState.OPEN
      ? get(streamAtom).notebook
      : null,
  );
  const documentAtom = atom(
    (get) => get(streamAtom).resources.document.current,
  );
  const attachmentsAtom = atom((get) =>
    get(readyAtom) && get(connectionAtom).state === ConnectionState.OPEN
      ? get(streamAtom).resources.attachments
      : attachments.initial,
  );
  let reconnect: (() => Promise<void>) | undefined;
  const client: NotebookClient = {
    connectionAtom,
    notebookAtom,
    documentAtom,
    attachmentsAtom,
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
    let streamKey: string | undefined;
    // The id of the last live event. Null before `ready` and after `reset`.
    let cursor: string | null = null;
    const transport = createTransport(() => {
      const next = new URL(url());
      next.searchParams.delete("cursor");
      if (signal.aborted) {
        return next.toString();
      }
      // A cursor is useful with the state that produced it, which a change
      // of session or notebook invalidates. Authentication may change freely.
      const identity = new URL(next);
      identity.searchParams.delete("access_token");
      identity.searchParams.sort();
      const key = identity.toString();
      const current = store.get(streamAtom);
      // A live stream keeps its state and resumes from the cursor. An
      // incomplete snapshot starts over.
      const state =
        key !== streamKey || current.phase === "snapshot"
          ? reducer.initial
          : current;
      if (state.phase === "snapshot") {
        cursor = null;
      }
      streamKey = key;
      store.set(readyAtom, false);
      store.set(streamAtom, state);
      if (cursor !== null) {
        next.searchParams.set("cursor", cursor);
      }
      return next.toString();
    });
    const setStatus = (status: ConnectionStatus) => {
      store.set(readyAtom, false);
      store.set(connectionAtom, status);
    };
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
        const state = store.get(streamAtom);
        if (
          state.phase === "live" &&
          event.id === undefined &&
          !UNCURSORED.has(event.event)
        ) {
          throw new Error("Live notebook event is missing its cursor");
        }
        if (event.event !== "marimo" && event.event !== "unknown") {
          store.set(streamAtom, reducer.reduce(state, event));
        }
        if (event.event === "reset") {
          cursor = null;
        } else if (event.event === "ready" || state.phase === "live") {
          cursor = event.id ?? cursor;
        }
        if (event.event === "ready" || event.event === "reset") {
          store.set(readyAtom, event.event === "ready");
        }
      } catch (error) {
        Logger.error("Failed to decode notebook message", error);
        store.set(streamAtom, reducer.initial);
        cursor = null;
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
        store.set(streamAtom, reducer.initial);
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
