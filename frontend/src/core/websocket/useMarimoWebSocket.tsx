/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketClosedReason, WebSocketState } from "./types";
import { useAtom } from "jotai";
import { connectionAtom } from "../network/connection";
import { useWebSocket } from "@/core/websocket/useWebSocket";
import { logNever } from "@/utils/assertNever";
import { useCellActions } from "@/core/cells/cells";
import { AUTOCOMPLETER } from "@/core/codemirror/completion/Autocompleter";
import type { OperationMessage } from "@/core/kernel/messages";
import type { CellData } from "../cells/types";
import { useErrorBoundary } from "react-error-boundary";
import { Logger } from "@/utils/Logger";
import { type LayoutState, useLayoutActions } from "../layout/layout";
import { useVariablesActions } from "../variables/state";
import { toast } from "@/components/ui/use-toast";
import { renderHTML } from "@/plugins/core/RenderHTML";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import { prettyError } from "@/utils/errors";
import { isStaticNotebook } from "../static/static-state";
import { useRef } from "react";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import type { SessionId } from "../kernel/session";
import { useBannersActions } from "../errors/state";
import { useAlertActions } from "../alerts/state";
import { generateUUID } from "@/utils/uuid";
import { createWsUrl } from "./createWsUrl";
import { useSetAppConfig } from "../config/config";
import {
  handleCellOperation,
  handleKernelReady,
  handleRemoveUIElements,
} from "../kernel/handlers";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import type { JsonString } from "@/utils/json/base64";
import { useDatasetsActions } from "../datasets/state";

/**
 * WebSocket that connects to the Marimo kernel and handles incoming messages.
 */
export function useMarimoWebSocket(opts: {
  sessionId: SessionId;
  autoInstantiate: boolean;
  setCells: (cells: CellData[], layout: LayoutState) => void;
}) {
  // Track whether we want to try reconnecting.
  const shouldTryReconnecting = useRef<boolean>(true);
  const { autoInstantiate, sessionId, setCells } = opts;
  const { showBoundary } = useErrorBoundary();

  const { handleCellMessage } = useCellActions();
  const setAppConfig = useSetAppConfig();
  const { setVariables, setMetadata } = useVariablesActions();
  const { addColumnPreview } = useDatasetsActions();
  const { addDatasets } = useDatasetsActions();
  const { setLayoutData } = useLayoutActions();
  const [connection, setConnection] = useAtom(connectionAtom);
  const { addBanner } = useBannersActions();
  const { addPackageAlert } = useAlertActions();

  const handleMessage = (e: MessageEvent<JsonString<OperationMessage>>) => {
    const msg = jsonParseWithSpecialChar(e.data);
    switch (msg.op) {
      case "reload":
        window.location.reload();
        return;
      case "kernel-ready":
        handleKernelReady(msg.data, {
          autoInstantiate,
          setCells,
          setLayoutData,
          setAppConfig,
          onError: showBoundary,
        });
        return;

      case "completed-run":
        return;
      case "interrupted":
        return;

      case "remove-ui-elements":
        handleRemoveUIElements(msg.data);
        return;

      case "completion-result":
        AUTOCOMPLETER.resolve(msg.data.completion_id, msg.data);
        return;
      case "function-call-result":
        FUNCTIONS_REGISTRY.resolve(msg.data.function_call_id, msg.data);
        return;
      case "cell-op":
        handleCellOperation(msg.data, handleCellMessage);
        return;

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
      case "missing-package-alert":
        addPackageAlert({
          ...msg.data,
          kind: "missing",
        });
        return;
      case "installing-package-alert":
        addPackageAlert({
          ...msg.data,
          kind: "installing",
        });
        return;
      case "query-params-append":
        queryParamHandlers.append(msg.data);
        return;

      case "query-params-set":
        queryParamHandlers.set(msg.data);
        return;

      case "query-params-delete":
        queryParamHandlers.delete(msg.data);
        return;

      case "query-params-clear":
        queryParamHandlers.clear();
        return;

      case "datasets":
        addDatasets(msg.data);
        return;
      case "data-column-preview":
        addColumnPreview(msg.data);
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
      setConnection({ state: WebSocketState.OPEN });
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
          setConnection({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.ALREADY_RUNNING,
            reason: "another browser tab is already connected to the kernel",
          });
          ws.close(); // close to prevent reconnecting
          return;

        case "MARIMO_WRONG_KERNEL_ID":
        case "MARIMO_SHUTDOWN":
          Logger.warn("WebSocket closed", e.reason);
          setConnection({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.KERNEL_DISCONNECTED,
            reason: "kernel not found",
          });
          ws.close(); // close to prevent reconnecting
          return;

        case "MARIMO_MALFORMED_QUERY":
          setConnection({
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
          setConnection({ state: WebSocketState.CONNECTING });
          tryReconnecting(e.code, e.reason);
      }
    },

    /**
     * When we encounter an error, we should close the connection.
     */
    onError: (e) => {
      Logger.warn("WebSocket error", e);
      setConnection({
        state: WebSocketState.CLOSED,
        code: WebSocketClosedReason.KERNEL_DISCONNECTED,
        reason: "kernel not found",
      });
      tryReconnecting();
    },
  });

  return { connection };
}
