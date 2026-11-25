/* Copyright 2026 Marimo. All rights reserved. */

import { invalidatePackageData } from "@/core/packages/package-data";
import { atom, useAtom, useAtomValue, useSetAtom, useStore } from "jotai";
import { useEffect, useLayoutEffect, useMemo } from "react";
import { toast } from "@/components/ui/use-toast";
import { notebookAtom, useReducerActions } from "@/core/cells/cells";
import { useStagedAICellsActions } from "@/core/ai/staged-cells";
import { followDocument } from "@/core/cells/document";
import { SCRATCH_CELL_ID, type CellId } from "@/core/cells/ids";
import { AUTOCOMPLETER } from "@/core/codemirror/completion/Autocompleter";
import { createDocumentModel } from "@/core/notebook/document";
import type { NotificationPayload } from "@/core/kernel/messages";
import { useNotebookReplica } from "@/core/session/useNotebookReplica";
import { renderHTML } from "@/plugins/core/RenderHTML";
import {
  handleWidgetMessage,
  WIDGET_REGISTRY,
} from "@/plugins/impl/anywidget/registry";
import { logNever } from "@/utils/assertNever";
import { prettyError } from "@/utils/errors";
import { safeExtractSetUIElementMessageBuffers } from "@/utils/json/base64";
import { Logger } from "@/utils/Logger";
import { Objects } from "@/utils/objects";
import { reloadSafe } from "@/utils/reload-safe";
import { useAlertActions } from "../alerts/state";
import { cacheInfoAtom } from "../cache/requests";
import { useRunsActions } from "../cells/runs";
import { focusAndScrollCellOutputIntoView } from "../cells/scrollCellIntoView";
import {
  breakpointsAtom,
  pendingPdbInputAtom,
  setActiveLine,
} from "../codemirror/cells/debugger-state";
import { notebookCells } from "../cells/utils";
import { capabilitiesAtom } from "../config/capabilities";
import { connectionTransportTypeAtom } from "../config/config";
import { useDataSourceActions } from "../datasets/data-source-connections";
import { invalidateDataSourceDiscovery } from "../datasets/data-source-discovery";
import type { ConnectionName } from "../datasets/engines";
import {
  DiscoverDataSources,
  PreviewSQLSchemaList,
  PreviewSQLTable,
  PreviewSQLTableList,
  ValidateSQL,
} from "../datasets/request-registry";
import { useDatasetsActions } from "../datasets/state";
import { UI_ELEMENT_REGISTRY } from "../dom/uiregistry";
import { kernelStartupErrorAtom, useBannersActions } from "../errors/state";
import { FUNCTIONS_REGISTRY } from "../functions/FunctionRegistry";
import { handleKernelReady, handleRemoveUIElements } from "../kernel/handlers";
import { queryParamHandlers } from "../kernel/queryParamHandlers";
import {
  type SessionId,
  type StableSessionId,
  stableSessionIdAtom,
} from "../kernel/session";
import { cellError } from "../executions/output";
import { getCellLogsForMessage } from "../cells/logs";
import { initialRunCompletedAtom } from "../kernel/state";
import { useLayoutActions } from "../layout/state";
import { kioskModeAtom } from "../mode";
import { connectionAtom, startupProgressAtom } from "../network/connection";
import { savedLayoutAtom } from "../saving/state";
import type { RequestId } from "../network/DeferredRequestRegistry";
import { useRuntimeManager } from "../runtime/config";
import { SECRETS_REGISTRY } from "../secrets/request-registry";
import { isStaticNotebook } from "../static/static-state";
import { VirtualFileTracker } from "../static/virtual-file-tracker";
import {
  DownloadStorage,
  ListStorageEntries,
} from "../storage/request-registry";
import { useStorageActions } from "../storage/state";
import { variableBindingsAtom } from "../variables/state";
import {
  activeDocumentModelAtom,
  confirmedDocumentAtom,
} from "./active-notebook";
import { completedAt, startedAt } from "@/core/notebook/replica";
import { executionSource } from "@/core/executions";
import { embeddedSnapshotAtom } from "./embedded";
import { WebSocketClosedReason, ConnectionState } from "./types";

/** Coordinate session startup and apply notifications to the editor. */
export function useNotebookSession(opts: { sessionId: SessionId }) {
  const { sessionId } = opts;
  const store = useStore();

  const {
    showCommandOutput,
    hideConsoleInputs,
    clearDebuggerOutput,
    reconcileDocument,
    resetCellRuntimes,
  } = useReducerActions();
  const { reconcileStagedCells } = useStagedAICellsActions();
  const { addExecution } = useRunsActions();
  const setInitialRunCompleted = useSetAtom(initialRunCompletedAtom);
  const { addColumnPreview, addDatasets, removeDatasetsForVariables } =
    useDatasetsActions();
  const { addDataSourceConnection, removeConnectionsForVariables } =
    useDataSourceActions();
  const { setLayoutData } = useLayoutActions();
  const [connection, setConnection] = useAtom(connectionAtom);
  const updateStartupProgress = useSetAtom(startupProgressAtom);
  const { addBanner } = useBannersActions();
  const {
    addMissingPackageAlert,
    updateEnvironment,
    setEnvironment,
    addStartupLog,
  } = useAlertActions();
  const setKioskMode = useSetAtom(kioskModeAtom);
  const setStableSessionId = useSetAtom(stableSessionIdAtom);
  const setCapabilities = useSetAtom(capabilitiesAtom);
  const runtimeManager = useRuntimeManager();
  const transportType = useAtomValue(connectionTransportTypeAtom);
  const setCacheInfo = useSetAtom(cacheInfoAtom);
  const setKernelStartupError = useSetAtom(kernelStartupErrorAtom);
  const { setNamespaces: setStorageNamespaces, removeNamespacesForVariables } =
    useStorageActions();

  const handleNotification = (msg: NotificationPayload) => {
    switch (msg.data.op) {
      case "reload":
        reloadSafe();
        return;
      case "startup-progress": {
        const { phase } = msg.data;
        updateStartupProgress(msg.data);
        setConnection((previous) =>
          previous.state === ConnectionState.OPEN ||
          (previous.state === ConnectionState.CONNECTING &&
            previous.phase === phase)
            ? previous
            : { state: ConnectionState.CONNECTING, phase },
        );
        return;
      }
      case "kernel-ready": {
        setInitialRunCompleted(msg.data.resumed);
        const layout = handleKernelReady(msg.data, {
          cells: notebookCells(store.get(notebookAtom)),
          resetCellRuntimes,
          setLayoutData,
          setCapabilities,
        });
        store.set(savedLayoutAtom, layout);
        if (!msg.data.resumed) {
          // A freshly started kernel may expose a different environment
          // (e.g. new env vars); re-run discovery instead of reusing stale
          // suggestions from the previous kernel instance.
          invalidateDataSourceDiscovery();
        }
        setKioskMode(msg.data.kiosk);
        setStableSessionId(
          (msg.data.stable_session_id as StableSessionId | null | undefined) ??
            null,
        );
        setActiveLine(null);
        store.set(pendingPdbInputAtom, null);
        return;
      }

      case "pdb-input": {
        const { cell_id, input_id } = msg.data;
        store.set(
          pendingPdbInputAtom,
          input_id === null ? null : { cellId: cell_id, inputId: input_id },
        );
        return;
      }

      case "completed-run":
        setInitialRunCompleted(true);
        return;

      case "kernel-startup-error":
        // Full error received via message before websocket close
        setKernelStartupError(msg.data.error);
        return;

      case "send-ui-element-message": {
        const uiElement = msg.data.ui_element;
        if (uiElement) {
          const buffers = safeExtractSetUIElementMessageBuffers(msg.data);
          UI_ELEMENT_REGISTRY.broadcastMessage(
            uiElement,
            msg.data.message,
            buffers,
          );
        }
        return;
      }

      case "model-lifecycle":
        handleWidgetMessage(WIDGET_REGISTRY, msg.data);
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
      case "console-inputs-cleared":
        hideConsoleInputs({
          cellId: msg.data.cell_id,
          executionId: msg.data.execution_id,
          inputIds: msg.data.input_ids,
        });
        return;
      case "callback-output":
        VirtualFileTracker.INSTANCE.trackCallbackOutput(msg.data);
        showCommandOutput(msg.data);
        return;
      case "pdb-output":
        showCommandOutput(msg.data);
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
        addMissingPackageAlert({
          ...msg.data,
          kind: "missing",
        });
        return;
      case "environment-operation":
        if (
          msg.data.source === "kernel" &&
          msg.data.status.kind !== "running"
        ) {
          invalidatePackageData();
        }
        updateEnvironment(msg.data);
        return;
      case "environment-state":
        setEnvironment(msg.data);
        if (msg.data.source === "kernel") {
          invalidatePackageData();
        }
        return;
      case "startup-logs":
        addStartupLog({
          content: msg.data.content,
          status: msg.data.status,
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
        PreviewSQLTable.resolve(msg.data.request_id, msg.data);
        return;
      case "sql-table-list-preview":
        PreviewSQLTableList.resolve(msg.data.request_id, msg.data);
        return;
      case "sql-schema-list-preview":
        PreviewSQLSchemaList.resolve(msg.data.request_id, msg.data);
        return;
      case "validate-sql-result":
        ValidateSQL.resolve(msg.data.request_id as RequestId, msg.data);
        return;
      case "data-source-discovery-result":
        DiscoverDataSources.resolve(msg.data.request_id as RequestId, msg.data);
        return;
      case "secret-keys-result":
        SECRETS_REGISTRY.resolve(msg.data.request_id, msg.data);
        return;
      case "cache-info":
        setCacheInfo(msg.data);
        return;
      case "data-source-connections":
        addDataSourceConnection({
          connections: msg.data.connections.map((conn) => ({
            ...conn,
            name: conn.name as ConnectionName,
          })),
        });
        return;
      case "storage-namespaces":
        setStorageNamespaces(msg.data);
        return;
      case "storage-entries":
        ListStorageEntries.resolve(msg.data.request_id as RequestId, msg.data);
        return;
      case "storage-download-ready":
        DownloadStorage.resolve(msg.data.request_id as RequestId, msg.data);
        return;

      case "focus-cell":
        focusAndScrollCellOutputIntoView(msg.data.cell_id);
        return;
      case "breakpoints":
        store.set(
          breakpointsAtom,
          new Map(
            Objects.entries<CellId, number[]>(msg.data.breakpoints).map(
              ([cellId, lines]) => [cellId, new Set(lines)],
            ),
          ),
        );
        return;
      case "active-line":
        setActiveLine(
          msg.data.line == null
            ? null
            : { cellId: msg.data.cell_id, line: msg.data.line },
        );
        return;
      case "consumer-capabilities":
        setKioskMode(!msg.data.consumer_capabilities.edit);
        if (!msg.data.consumer_capabilities.edit) {
          store.set(pendingPdbInputAtom, null);
          clearDebuggerOutput();
        }
        return;
      default:
        logNever(msg.data);
    }
  };

  const onMessageError = (error: unknown) => {
    toast({
      title: "Failed to handle message",
      description: prettyError(error),
      variant: "danger",
    });
  };
  const replica = useNotebookReplica({
    static: isStaticNotebook(),
    snapshot: useAtomValue(embeddedSnapshotAtom),
    transportType,
    url: () =>
      transportType === "sse"
        ? runtimeManager.getSseURL(sessionId).toString()
        : runtimeManager.getWsURL(sessionId).toString(),
    // SSE uses headers for auth. WebSockets carry the token in the URL.
    headers: () => runtimeManager.headers(),
    notebookUrl: (notebookId) => runtimeManager.getNotebookURL(notebookId),
    // Only the host's transports read the URL, so static and WASM never wait.
    waitUntilReady: async () => {
      if (!runtimeManager.isSameOrigin) {
        await runtimeManager.waitForHealthy();
      }
    },
    checkHealth: () => runtimeManager.reconcileFromHealth(),
    onExecution: (record) => {
      const cellId = record.cell_id ?? SCRATCH_CELL_ID;
      const time = completedAt(record) ?? startedAt(record);
      const timestamp =
        time === null ? Date.now() / 1000 : Date.parse(time) / 1000;
      if (
        record.state.status === "completed" &&
        record.state.outcome.kind === "failed"
      ) {
        getCellLogsForMessage({
          cell_id: cellId,
          timestamp,
          output: {
            channel: "marimo-error",
            mimetype: "application/vnd.marimo+error",
            data: [cellError(record.state.outcome.error)],
            timestamp,
          },
        });
      }
      addExecution({
        record,
        code: executionSource(record, store.get(confirmedDocumentAtom)?.cells),
        receivedAt: timestamp,
      });
    },
    onNotification: (notification) => {
      try {
        handleNotification(notification);
      } catch (error) {
        Logger.error("Failed to handle notification", notification, error);
        onMessageError(error);
      }
    },
  });

  // Discovery can precede a binding. Remove only resources whose binding disappeared.
  useLayoutEffect(() => {
    let previous = store.get(variableBindingsAtom);
    return store.sub(variableBindingsAtom, () => {
      const current = store.get(variableBindingsAtom);
      const removed = new Set<string>();
      for (const [cellId, bindings] of previous ?? []) {
        const next = current?.get(cellId);
        if (bindings === next) {
          continue;
        }
        for (const [id, binding] of bindings) {
          if (!next?.has(id)) {
            removed.add(binding.name);
          }
        }
      }
      previous = current;
      if (removed.size > 0) {
        removeDatasetsForVariables(removed);
        removeConnectionsForVariables(removed);
        removeNamespacesForVariables(removed);
      }
    });
  }, [
    store,
    removeDatasetsForVariables,
    removeConnectionsForVariables,
    removeNamespacesForVariables,
  ]);

  const documentModel = useMemo(
    () =>
      createDocumentModel({
        store,
        documentAtom: replica.documentAtom,
        shownDocumentAtom: replica.shownDocumentAtom,
        backendAtom: replica.backendAtom,
      }),
    [store, replica],
  );
  // Edits outlive reconnects and end with the session. The notebook's cells
  // follow the document for as long as the session is mounted.
  useEffect(() => {
    const controller = new AbortController();
    documentModel.start({ signal: controller.signal });
    store.set(activeDocumentModelAtom, documentModel);
    followDocument({
      store,
      model: documentModel,
      reconcile: (document) => {
        reconcileDocument(document);
        reconcileStagedCells(document.order);
      },
      signal: controller.signal,
    });
    return () => {
      controller.abort();
      if (store.get(activeDocumentModelAtom) === documentModel) {
        store.set(activeDocumentModelAtom, null);
      }
    };
  }, [documentModel, store, reconcileDocument, reconcileStagedCells]);

  // Subscribe before passive connection setup: static/WASM transports can emit synchronously.
  useLayoutEffect(() => {
    const readyAtom = atom((get) => get(replica.notebookAtom) !== null);
    const updateConnection = () => {
      let status = store.get(replica.connectionAtom);
      if (status.state === ConnectionState.NOT_STARTED) {
        return;
      }
      if (status.state === ConnectionState.OPEN) {
        updateStartupProgress(null);
        // The stream's snapshot, not the socket, establishes readiness. A
        // static page has a snapshot but no host to be connected to.
        if (isStaticNotebook()) {
          return;
        }
        if (store.get(readyAtom)) {
          setKernelStartupError(null);
          setConnection({ state: ConnectionState.OPEN });
          return;
        }
        status = { state: ConnectionState.CONNECTING };
      }
      if (status.state === ConnectionState.CONNECTING) {
        setKernelStartupError(null);
      }
      setConnection((previous) => {
        if (
          status.state === ConnectionState.CLOSED &&
          status.code === WebSocketClosedReason.KERNEL_STARTUP_ERROR &&
          (previous.state === ConnectionState.CONNECTING ||
            previous.state === ConnectionState.CLOSED)
        ) {
          return { ...status, phase: previous.phase };
        }
        if (
          status.state === ConnectionState.CONNECTING &&
          (previous.state === ConnectionState.OPEN ||
            (previous.state === ConnectionState.CONNECTING &&
              previous.phase === "reconnecting"))
        ) {
          return { ...status, phase: "reconnecting" };
        }
        return status;
      });
    };
    const unsubscribes = [
      store.sub(replica.connectionAtom, updateConnection),
      store.sub(readyAtom, updateConnection),
      // Same-session reconnects replay only the prompt that is still pending.
      store.sub(replica.generationAtom, () =>
        store.set(pendingPdbInputAtom, null),
      ),
    ];
    updateConnection();
    return () => unsubscribes.forEach((unsubscribe) => unsubscribe());
  }, [
    replica,
    store,
    setConnection,
    setKernelStartupError,
    updateStartupProgress,
  ]);

  return { replica, documentModel, connection, reconnect: replica.reconnect };
}
