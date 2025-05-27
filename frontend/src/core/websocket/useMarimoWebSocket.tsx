/* Copyright 2024 Marimo. All rights reserved. */
import { WebSocketClosedReason, WebSocketState } from "./types";
import { useAtom, useSetAtom } from "jotai";
import { connectionAtom } from "../network/connection";
import { useWebSocket } from "@/core/websocket/useWebSocket";
import { logNever } from "@/utils/assertNever";
import { getNotebook, useCellActions } from "@/core/cells/cells";
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
import {
  PreviewSQLTable,
  PreviewSQLTableList,
} from "../datasets/request-registry";
import { prettyError } from "@/utils/errors";
import { isStaticNotebook } from "../static/static-state";
import { useRef } from "react";
import { jsonParseWithSpecialChar } from "@/utils/json/json-parser";
import type { SessionId } from "../kernel/session";
import { useBannersActions } from "../errors/state";
import { useAlertActions } from "../alerts/state";
import { createWsUrl } from "./createWsUrl";
import { useSetAppConfig } from "../config/config";
import {
  handleCellOperation,
  handleKernelReady,
  handleRemoveUIElements,
} from "../kernel/handlers";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import type { Base64String, JsonString } from "@/utils/json/base64";
import { useDatasetsActions } from "../datasets/state";
import type { RequestId } from "../network/DeferredRequestRegistry";
import type { VariableName } from "../variables/types";
import type { CellId, UIElementId } from "../cells/ids";
import { kioskModeAtom } from "../mode";
import { focusAndScrollCellOutputIntoView } from "../cells/scrollCellIntoView";
import { capabilitiesAtom } from "../config/capabilities";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { reloadSafe } from "@/utils/reload-safe";
import { useRunsActions } from "../cells/runs";
import {
  type ConnectionName,
  useDataSourceActions,
} from "../datasets/data-source-connections";
import { SECRETS_REGISTRY } from "../secrets/request-registry";
import {
  handleWidgetMessage,
  isMessageWidgetState,
  MODEL_MANAGER,
} from "@/plugins/impl/anywidget/model";

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

  const { handleCellMessage, setCellCodes, setCellIds } = useCellActions();
  const { addCellOperation } = useRunsActions();
  const setAppConfig = useSetAppConfig();
  const { setVariables, setMetadata } = useVariablesActions();
  const { addColumnPreview } = useDatasetsActions();
  const { addDatasets, filterDatasetsFromVariables } = useDatasetsActions();
  const { addDataSourceConnection, filterDataSourcesFromVariables } =
    useDataSourceActions();
  const { setLayoutData } = useLayoutActions();
  const [connection, setConnection] = useAtom(connectionAtom);
  const { addBanner } = useBannersActions();
  const { addPackageAlert } = useAlertActions();
  const setKioskMode = useSetAtom(kioskModeAtom);
  const setCapabilities = useSetAtom(capabilitiesAtom);

  const handleMessage = (e: MessageEvent<JsonString<OperationMessage>>) => {
    const msg = jsonParseWithSpecialChar(e.data);
    switch (msg.op) {
      case "reload":
        reloadSafe();
        return;
      case "kernel-ready":
        handleKernelReady(msg.data, {
          autoInstantiate,
          setCells,
          setLayoutData,
          setAppConfig,
          setCapabilities,
          onError: showBoundary,
        });
        setKioskMode(msg.data.kiosk);
        return;

      case "completed-run":
        return;
      case "interrupted":
        return;

      case "send-ui-element-message": {
        const modelId = msg.data.model_id;
        const uiElement = msg.data.ui_element;
        const message = msg.data.message;
        const buffers = (msg.data.buffers ?? []) as Base64String[];

        if (modelId && isMessageWidgetState(message)) {
          handleWidgetMessage(modelId, message, buffers, MODEL_MANAGER);
        }

        if (uiElement) {
          UI_ELEMENT_REGISTRY.broadcastMessage(
            uiElement as UIElementId,
            msg.data.message,
            buffers,
          );
        }

        return;
      }

      case "remove-ui-elements":
        handleRemoveUIElements(msg.data);
        return;

      case "completion-result":
        AUTOCOMPLETER.resolve(msg.data.completion_id as RequestId, msg.data);
        return;
      case "function-call-result":
        FUNCTIONS_REGISTRY.resolve(
          msg.data.function_call_id as RequestId,
          msg.data,
        );
        return;
      case "cell-op": {
        handleCellOperation(msg.data, handleCellMessage);
        const cellData = getNotebook().cellData[msg.data.cell_id as CellId];
        if (!cellData) {
          return;
        }
        addCellOperation({ cellOperation: msg.data, code: cellData.code });
        return;
      }

      case "variables":
        setVariables(
          msg.data.variables.map((v) => ({
            name: v.name as VariableName,
            declaredBy: v.declared_by as CellId[],
            usedBy: v.used_by as CellId[],
          })),
        );
        filterDatasetsFromVariables(
          msg.data.variables.map((v) => v.name as VariableName),
        );
        filterDataSourcesFromVariables(
          msg.data.variables.map((v) => v.name as VariableName),
        );
        return;
      case "variable-values":
        setMetadata(
          msg.data.variables.map((v) => ({
            name: v.name as VariableName,
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
        addBanner(msg.data);
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
      case "sql-table-preview":
        PreviewSQLTable.resolve(msg.data.request_id as RequestId, msg.data);
        return;
      case "sql-table-list-preview":
        PreviewSQLTableList.resolve(msg.data.request_id as RequestId, msg.data);
        return;
      case "secret-keys-result":
        SECRETS_REGISTRY.resolve(msg.data.request_id as RequestId, msg.data);
        return;
      case "data-source-connections":
        addDataSourceConnection({
          connections: msg.data.connections.map((conn) => ({
            ...conn,
            name: conn.name as ConnectionName,
          })),
        });
        return;

      case "reconnected":
        return;

      case "focus-cell":
        focusAndScrollCellOutputIntoView(msg.data.cell_id as CellId);
        return;
      case "update-cell-codes":
        setCellCodes({
          codes: msg.data.codes,
          ids: msg.data.cell_ids as CellId[],
          codeIsStale: msg.data.code_is_stale,
        });
        return;
      case "update-cell-ids":
        setCellIds({ cellIds: msg.data.cell_ids as CellId[] });
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
        Logger.error("Failed to handle message", error);
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
      Logger.warn("WebSocket closed", e.code, e.reason);
      switch (e.reason) {
        case "MARIMO_ALREADY_CONNECTED":
          setConnection({
            state: WebSocketState.CLOSED,
            code: WebSocketClosedReason.ALREADY_RUNNING,
            reason: "another browser tab is already connected to the kernel",
            canTakeover: true,
          });
          ws.close(); // close to prevent reconnecting
          return;

        case "MARIMO_WRONG_KERNEL_ID":
        case "MARIMO_NO_FILE_KEY":
        case "MARIMO_NO_SESSION_ID":
        case "MARIMO_NO_SESSION":
        case "MARIMO_SHUTDOWN":
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
