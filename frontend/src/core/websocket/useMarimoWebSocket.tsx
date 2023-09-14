/* Copyright 2023 Marimo. All rights reserved. */
import { WebSocketClosedReason, WebSocketState } from "./types";
import { useAtom } from "jotai";
import { connectionAtom } from "../state/connection";
import { useWebSocket } from "@/core/websocket/useWebSocket";
import { logNever } from "@/utils/assertNever";
import { useCellActions } from "@/core/state/cells";
import { RuntimeState } from "@/core/RuntimeState";
import { COMPLETION_REQUESTS } from "@/core/codemirror/completion/CompletionRequests";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { OperationMessage } from "@/core/kernel/messages";
import { sendInstantiate } from "../network/requests";
import { CellId } from "../model/ids";
import { CellState, createCell } from "../model/cells";
import { useErrorBoundary } from "react-error-boundary";
import { Logger } from "@/utils/Logger";

/**
 * WebSocket that connects to the Marimo kernel and handles incoming messages.
 */
export function useMarimoWebSocket(opts: {
  sessionId: string;
  setCells: (cells: CellState[]) => void;
  setInitialCodes: (codes: string[]) => void;
}) {
  const { sessionId, setCells, setInitialCodes } = opts;
  const { showBoundary } = useErrorBoundary();

  const { handleCellMessage } = useCellActions();
  const [connStatus, setConnStatus] = useAtom(connectionAtom);

  const ws = useWebSocket({
    /**
     * Unique URL for this session.
     */
    url: createWsUrl(sessionId),

    /**
     * Open callback. Set the connection status to open.
     */
    onOpen: () => {
      setConnStatus({ state: WebSocketState.OPEN });
    },

    /**
     * Message callback. Handle messages sent by the kernel.
     */
    onMessage: (e: MessageEvent<string>) => {
      const msg = JSON.parse(e.data) as OperationMessage;
      switch (msg.op) {
        case "kernel-ready": {
          const { codes, names } = msg.data;

          // TODO(akshayka): Get rid of this once the kernel sends cell IDs in
          // kernel-ready.
          CellId.reset();

          // Set the initial codes and cells
          const cells = codes.map((code, i) =>
            createCell({
              key: CellId.create(),
              code,
              initialContents: code,
              name: names[i],
            })
          );
          setCells(cells);
          setInitialCodes(codes);

          // Auto-instantiate, in future this can be configurable
          // or include initial values
          const objectIds: string[] = [];
          const values: unknown[] = [];
          // If we already have values for some objects, we should
          // send them to the kernel. This may happen after re-connecting
          // to the kernel after the computer wakes from sleep.
          UI_ELEMENT_REGISTRY.entries.forEach((entry, objectId) => {
            objectIds.push(objectId);
            values.push(entry.value);
          });
          // Start the run
          RuntimeState.INSTANCE.registerRunStart();
          // Send the instantiate message
          sendInstantiate({ objectIds, values }).catch((error) => {
            showBoundary(new Error("Failed to instantiate", { cause: error }));
          });
          return;
        }
        case "completed-run":
        case "interrupted":
          if (msg.op === "completed-run") {
            RuntimeState.INSTANCE.registerRunEnd();
          }

          if (!RuntimeState.INSTANCE.running()) {
            RuntimeState.INSTANCE.flushUpdates();
          }
          return;
        case "remove-ui-elements": {
          // This removes the element from the registry to (1) clean-up
          // memory and (2) make sure that the old value doesn't get re-used
          // if the same cell-id is later reused for another element.
          const { cell_id } = msg.data;
          UI_ELEMENT_REGISTRY.removeElementsByCell(cell_id);
          return;
        }
        case "completion-result":
          COMPLETION_REQUESTS.resolve(msg.data);
          return;
        case "cell-op": {
          /* Register a state transition for a cell.
           *
           * The cell may have a new output, a new console output,
           * it may have been queued, it may have started running, or
           * it may have stopped running. Each of these things
           * affects how the cell should be rendered.
           */
          const body = msg.data;
          handleCellMessage({ cellId: body.cell_id, message: body });
          return;
        }
        default:
          logNever(msg);
      }
    },

    /**
     * Handle a close event. We may want to reconnect.
     */
    onClose: (e) => {
      switch (e.reason) {
        case "MARIMO_ALREADY_CONNECTED":
          setConnStatus({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.ALREADY_RUNNING,
            reason: "another browser tab is already connected to the kernel",
          });
          ws.current?.close(); // close to prevent reconnecting
          return;

        case "MARIMO_WRONG_KERNEL_ID":
        case "MARIMO_SHUTDOWN":
          Logger.warn("WebSocket closed", e.reason);
          setConnStatus({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.KERNEL_DISCONNECTED,
            reason: "kernel not found",
          });
          ws.current?.close(); // close to prevent reconnecting
          return;

        case "MARIMO_MALFORMED_QUERY":
          setConnStatus({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.MALFORMED_QUERY,
            reason:
              "the kernel did not recognize a request; please file a bug with marimo",
          });
          return;

        default:
          // Session should be valid
          // - browser tab might have been closed or re-opened
          // - computer might have just woken from sleep
          //
          // so try reconnecting.
          setConnStatus({ state: WebSocketState.CONNECTING });
          ws.current?.reconnect();
      }
    },

    /**
     * When we encounter an error, we should close the connection.
     */
    onError: (e) => {
      Logger.warn("WebSocket error", e);
      setConnStatus({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        reason: "kernel not found",
      });
      // Try reconnecting as this could have been a network error.
      ws.current?.reconnect();
    },
  });

  return { connStatus };
}

function createWsUrl(sessionId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  return `${protocol}://${window.location.host}/iosocket?session_id=${sessionId}`;
}
