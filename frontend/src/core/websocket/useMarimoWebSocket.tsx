/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketClosedReason, WebSocketState } from "./types";
import { useAtom, useSetAtom } from "jotai";
import { connectionAtom } from "../network/connection";
import { useWebSocket } from "@/core/websocket/useWebSocket";
import { logNever } from "@/utils/assertNever";
import { useCellActions } from "@/core/cells/cells";
import { RuntimeState } from "@/core/kernel/RuntimeState";
import { AUTOCOMPLETER } from "@/core/codemirror/completion/Autocompleter";
import { UI_ELEMENT_REGISTRY } from "@/core/dom/uiregistry";
import { OperationMessage } from "@/core/kernel/messages";
import { sendInstantiate } from "../network/requests";
import { CellData } from "../cells/types";
import { createCell } from "../cells/types";
import { useErrorBoundary } from "react-error-boundary";
import { Logger } from "@/utils/Logger";
import { layoutDataAtom, layoutViewAtom } from "../layout/layout";
import { deserializeLayout } from "@/components/editor/renderers/plugins";
import { useVariablesActions } from "../variables/state";
import { toast } from "@/components/ui/use-toast";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import { prettyError } from "@/utils/errors";
import { isStaticNotebook } from "../static/static-state";
import { useRef } from "react";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import { Objects } from "@/utils/objects";
import { SessionId } from "../kernel/session";
import { useBannersActions } from "../errors/state";
import { generateUUID } from "@/utils/uuid";

/**
 * WebSocket that connects to the Marimo kernel and handles incoming messages.
 */
export function useMarimoWebSocket(opts: {
  sessionId: SessionId;
  autoInstantiate: boolean;
  setCells: (cells: CellData[]) => void;
}) {
  // Track whether we want to try reconnecting.
  const shouldTryReconnecting = useRef<boolean>(true);
  const { autoInstantiate, sessionId, setCells } = opts;
  const { showBoundary } = useErrorBoundary();

  const { handleCellMessage } = useCellActions();
  const { setVariables, setMetadata } = useVariablesActions();
  const setLayoutView = useSetAtom(layoutViewAtom);
  const setLayoutData = useSetAtom(layoutDataAtom);
  const [connStatus, setConnStatus] = useAtom(connectionAtom);
  const { addBanner } = useBannersActions();

  const handleMessage = (e: MessageEvent<string>) => {
    const msg = jsonParseWithSpecialChar<OperationMessage>(e.data);
    switch (msg.op) {
      case "reload":
        window.location.reload();
        return;
      case "kernel-ready": {
        const {
          codes,
          names,
          layout,
          configs,
          resumed,
          ui_values,
          cell_ids,
          last_executed_code = {},
        } = msg.data;

        // Set the layout, initial codes, cells
        const cells = codes.map((code, i) => {
          const cellId = cell_ids[i];

          // A cell is stale if we did not auto-instantiate (i.e. nothing has run yet)
          // or if the code has changed since the last time it was run.
          let edited = false;
          if (autoInstantiate) {
            const lastCodeRun = last_executed_code[cellId];
            if (lastCodeRun) {
              edited = lastCodeRun !== code;
            }
          } else {
            edited = true;
          }

          return createCell({
            id: cellId,
            code,
            edited: edited,
            name: names[i],
            lastCodeRun: last_executed_code[cellId] ?? null,
            config: configs[i],
          });
        });

        if (layout) {
          setLayoutView(layout.type);
          setLayoutData(deserializeLayout(layout.type, layout.data, cells));
        }
        setCells(cells);

        // If resumed, we don't need to instantiate the UI elements,
        // and we should read in th existing values from the kernel.
        if (resumed) {
          for (const [objectId, value] of Objects.entries(ui_values || {})) {
            UI_ELEMENT_REGISTRY.set(objectId, value);
          }
          return;
        }

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
        // Send the instantiate message
        if (autoInstantiate) {
          // Start the run
          RuntimeState.INSTANCE.registerRunStart();
          sendInstantiate({ objectIds, values }).catch((error) => {
            RuntimeState.INSTANCE.registerRunEnd();
            showBoundary(new Error("Failed to instantiate", { cause: error }));
          });
        }
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
        VirtualFileTracker.INSTANCE.removeForCellId(cell_id);
        return;
      }
      case "completion-result":
        AUTOCOMPLETER.resolve(msg.data.completion_id, msg.data);
        return;
      case "function-call-result":
        FUNCTIONS_REGISTRY.resolve(msg.data.function_call_id, msg.data);
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
        VirtualFileTracker.INSTANCE.track(body);
        return;
      }
      case "variables":
        setVariables(
          msg.data.variables.map((v) => ({
            name: v.name,
            declaredBy: v.declared_by,
            usedBy: v.used_by,
          })),
        );
        return;
      case "variable-values":
        setMetadata(
          msg.data.variables.map((v) => ({
            name: v.name,
            dataType: v.datatype,
            value: v.value,
          })),
        );
        return;
      case "alert":
        toast({
          title: msg.data.title,
          description: renderHTML({
            html: msg.data.description,
          }),
          variant: msg.data.variant,
        });
        return;
      case "banner":
        addBanner({
          ...msg.data,
          id: generateUUID(),
        });
        return;
      default:
        logNever(msg);
    }
  };

  const tryReconnecting = (code?: number, reason?: string) => {
    // If not properly gated, we could try reconnecting forever if the
    // issue is not transient. So we want to try reconnecting only once after an
    // open connection is closed.
    if (shouldTryReconnecting.current) {
      shouldTryReconnecting.current = false;
      ws.reconnect(code, reason);
    }
  };

  const ws = useWebSocket({
    static: isStaticNotebook(),
    /**
     * Unique URL for this session.
     */
    url: createWsUrl(sessionId),

    /**
     * Open callback. Set the connection status to open.
     */
    onOpen: () => {
      // If we are open, we can reset our reconnecting flag.
      shouldTryReconnecting.current = true;
      setConnStatus({ state: WebSocketState.OPEN });
    },

    /**
     * Message callback. Handle messages sent by the kernel.
     */
    onMessage: (e) => {
      try {
        handleMessage(e);
      } catch (error) {
        toast({
          title: "Failed to handle message",
          description: prettyError(error),
          variant: "danger",
        });
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
          ws.close(); // close to prevent reconnecting
          return;

        case "MARIMO_WRONG_KERNEL_ID":
        case "MARIMO_SHUTDOWN":
          Logger.warn("WebSocket closed", e.reason);
          setConnStatus({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.KERNEL_DISCONNECTED,
            reason: "kernel not found",
          });
          ws.close(); // close to prevent reconnecting
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
          tryReconnecting(e.code, e.reason);
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
      tryReconnecting();
    },
  });

  return { connStatus };
}

function createWsUrl(sessionId: string): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";

  return `${protocol}://${window.location.host}/ws?session_id=${sessionId}`;
}
