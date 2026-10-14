/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta } from "@storybook/react-vite";
import { createStore, Provider, useAtomValue, useStore } from "jotai";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ConnectionNotice } from "@/components/editor/alerts/connection-notice";
import PackagesPanel from "@/components/editor/chrome/panels/packages-panel";
import { PanelSectionProvider } from "@/components/editor/chrome/panels/panel-context";
import { RuntimeStatusToggle } from "@/components/editor/chrome/panels/runtime-status-toggle";
import { SandboxController } from "@/components/editor/chrome/panels/sandbox-controller";
import { chromeAtom } from "@/components/editor/chrome/state";
import { Cell } from "@/components/editor/notebook-cell";
import { VerticalLayoutWrapper } from "@/components/editor/renderers/vertical-layout/vertical-layout-wrapper";
import { alertAtom } from "@/core/alerts/state";
import type { EnvironmentOperation } from "@/core/alerts/environment";
import {
  createNotebookActions,
  notebookAtom,
  notebookReducer,
} from "@/core/cells/cells";
import { userConfigAtom } from "@/core/config/config";
import {
  type AppConfig,
  AppConfigSchema,
  defaultUserConfig,
} from "@/core/config/config-schema";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { connectionAtom, startupProgressAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { createStaticRequests } from "@/core/network/requests-static";
import { sandboxActionsAtom, sandboxAtom } from "@/core/packages/sandbox-state";
import { filenameAtom } from "@/core/saving/file-state";
import {
  type ConnectionStatus,
  WebSocketClosedReason,
  WebSocketState,
} from "@/core/websocket/types";
import { HTTPError } from "@/utils/errors";

const manifest = `requires-python = ">=3.13"
dependencies = ["marimo", "polars", "rich==999.0.0"]

[tool.uv]
index-url = "https://pypi.org/simple"

[tool.notebook]
description = "Explore bike trips"
`;
const resolutionError = `No solution found when resolving dependencies:
  Because there is no version of rich==999.0.0 and your script depends
  on rich==999.0.0, your script's requirements are unsatisfiable.`;
const preparationOutput = `Using Python 3.13
Resolving notebook dependencies
Resolved 24 packages
Downloading polars
Downloading rich
Downloading marimo
Downloading pyzmq
Downloaded rich
Downloaded polars
Downloaded marimo
Preparing packages
Installing packages
`;

interface Props {
  surface: "notebook" | "packages" | "manifest";
  phase:
    | "preparing"
    | "starting"
    | "failed"
    | "ready"
    | "syncing"
    | "sync-failed"
    | "synced"
    | "restart-required";
  existingCells: boolean;
  backend: "uv" | "pixi" | null;
  saveResult: "success" | "failure" | "stale";
  theme: "light" | "dark";
  interactive: boolean;
  manual: boolean;
  detailsOpen: boolean;
}

function RuntimePreview({
  props,
  appConfig,
  reconnect,
}: {
  props: Props;
  appConfig: AppConfig;
  reconnect: () => Promise<void>;
}) {
  const chrome = useAtomValue(chromeAtom);
  const notebook = useAtomValue(notebookAtom);
  const userConfig = useAtomValue(userConfigAtom);
  const showPackages = props.surface === "packages" || chrome.isSidebarOpen;
  return (
    <div
      className="flex bg-background text-foreground border rounded min-h-[460px]"
      style={{ width: props.surface === "notebook" ? 1000 : 300 }}
      data-testid="sandbox-story"
    >
      {showPackages && props.surface !== "manifest" && (
        <aside className="flex flex-col w-[300px] shrink-0 border-r h-[520px]">
          <div className="flex items-center justify-between px-3 py-2 border-b text-sm">
            Packages
            <RuntimeStatusToggle section="sidebar" />
          </div>
          <PanelSectionProvider value="sidebar">
            <PackagesPanel />
          </PanelSectionProvider>
        </aside>
      )}
      {props.surface === "notebook" && (
        <div className="flex-1 min-w-0 pt-12">
          <ConnectionNotice appConfig={appConfig} onRetry={reconnect} />
          {notebook.cellIds.inOrderIds.map((cellId) => (
            <VerticalLayoutWrapper key={cellId} appConfig={appConfig}>
              <Cell
                cellId={cellId}
                theme={props.theme}
                mode="edit"
                showPlaceholder={false}
                canDelete={true}
                isCollapsed={false}
                collapseCount={0}
                canMoveX={false}
                userConfig={userConfig}
              />
            </VerticalLayoutWrapper>
          ))}
        </div>
      )}
    </div>
  );
}

function LifecycleControls({ backend }: { backend: Props["backend"] }) {
  const store = useStore();
  const [position, setPosition] = useState(0);
  const phases = backend
    ? (["preparing", "starting", "failed", "retrying", "ready"] as const)
    : (["starting", "failed", "retrying", "ready"] as const);
  const next = phases[(position + 1) % phases.length];
  const labels = {
    preparing: "Restart walkthrough",
    starting: "Start kernel",
    failed: "Simulate kernel failure",
    retrying: "Retry kernel",
    ready: "Kernel connected",
  };
  const advance = () => {
    setPosition((position + 1) % phases.length);
    store.set(
      kernelStartupErrorAtom,
      next === "failed" ? "The kernel process exited before connecting." : null,
    );
    const getNextConnectionStatus = (): ConnectionStatus => {
      if (next === "ready") {
        return { state: WebSocketState.OPEN };
      }
      if (next === "failed") {
        return {
          state: WebSocketState.CLOSED,
          code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
          phase: "starting-kernel",
          reason: "Kernel failed to start",
        };
      }
      return {
        state: WebSocketState.CONNECTING,
        phase:
          next === "preparing" ? "preparing-environment" : "starting-kernel",
      };
    };
    store.set(connectionAtom, getNextConnectionStatus());
    const getLogs = () => {
      if (next === "failed") {
        return "Kernel process exited\n";
      }
      if (next === "ready") {
        return "Kernel connected\n";
      }
      return "Launching kernel process\n";
    };
    store.set(startupProgressAtom, {
      phase: next === "preparing" ? "preparing-environment" : "starting-kernel",
      logs: getLogs(),
      log_mode: "replace",
    });
    store.set(alertAtom, (value) => ({
      ...value,
      environments: {
        ...value.environments,
        kernel: {
          ...value.environments.kernel,
          operations: value.environments.kernel.operations.map((operation) => ({
            ...operation,
            status:
              next === "preparing"
                ? { kind: "running" }
                : { kind: "succeeded" },
          })),
        },
      },
    }));
  };
  return (
    <div className="mb-4 flex items-center gap-3 text-xs text-muted-foreground">
      <Button variant="outline" size="xs" onClick={advance}>
        {labels[next]}
      </Button>
      <span>
        Story controls — advance the actual app through startup, failure, retry,
        and completion.
      </span>
    </div>
  );
}

function OpenManifest() {
  const actions = useAtomValue(sandboxActionsAtom);
  const opened = useRef(false);
  useEffect(() => {
    if (actions && !opened.current) {
      opened.current = true;
      void actions.editManifest();
    }
  }, [actions]);
  return null;
}

export function RuntimeStory(props: Props) {
  const [store] = useState(() => {
    const state = createStore();
    let currentManifest =
      props.phase === "failed"
        ? manifest
        : manifest.replace("rich==999.0.0", "rich>=13.0.0");
    const config = defaultUserConfig();
    state.set(userConfigAtom, {
      ...config,
      display: { ...config.display, theme: props.theme },
    });
    state.set(filenameAtom, "bike_trips.py");
    state.set(sandboxAtom, {
      backend: props.backend,
      manifest: currentManifest,
      filename: "bike_trips.py",
    });
    state.set(chromeAtom, {
      selectedPanel: "packages",
      isSidebarOpen: props.surface !== "notebook" || props.detailsOpen,
      isDeveloperPanelOpen: false,
      selectedDeveloperPanelTab: "errors",
    });
    const getConnectionPhase = ():
      | "preparing-environment"
      | "starting-kernel"
      | undefined => {
      if (!props.backend) {
        return undefined;
      }
      return props.phase === "preparing"
        ? "preparing-environment"
        : "starting-kernel";
    };
    const getInitialConnectionStatus = (): ConnectionStatus => {
      if (props.phase === "preparing" || props.phase === "starting") {
        return {
          state: WebSocketState.CONNECTING,
          phase: getConnectionPhase(),
        };
      }
      if (props.phase === "failed") {
        return {
          state: WebSocketState.CLOSED,
          code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
          reason: "Kernel startup failed",
          phase: props.backend ? "preparing-environment" : undefined,
        };
      }
      return { state: WebSocketState.OPEN };
    };
    state.set(connectionAtom, getInitialConnectionStatus());
    const getStartupError = () => {
      if (props.phase === "failed") {
        if (props.backend) {
          return resolutionError;
        }
        return "Python kernel exited before connecting.\nModuleNotFoundError: No module named 'ipykernel'";
      }
      return null;
    };
    state.set(kernelStartupErrorAtom, getStartupError());
    let syncStatus: EnvironmentOperation["status"] | null;
    if (props.phase === "syncing") {
      syncStatus = { kind: "running" };
    } else if (props.phase === "sync-failed") {
      syncStatus = { kind: "failed", error: resolutionError };
    } else if (props.phase === "restart-required") {
      syncStatus = {
        kind: "restart-required",
        reason:
          "The manifest requires Python 3.14. This kernel uses Python 3.13.",
      };
    } else if (props.phase === "synced") {
      syncStatus = { kind: "succeeded" };
    } else {
      syncStatus = null;
    }
    const getPreparationStatus = (): EnvironmentOperation["status"] => {
      if (props.phase === "failed") {
        return { kind: "failed", error: resolutionError };
      }
      if (props.phase === "preparing") {
        return { kind: "running" };
      }
      return { kind: "succeeded" };
    };
    state.set(alertAtom, (value) => ({
      ...value,
      environments: {
        ...value.environments,
        kernel: {
          restart_required: props.phase === "restart-required",
          operations: props.backend
            ? [
                {
                  operation_id: "story-preparation",
                  action: "prepare",
                  source: "kernel",
                  status: getPreparationStatus(),
                  packages: {},
                  logs: {
                    environment:
                      props.phase === "failed"
                        ? resolutionError
                        : preparationOutput,
                  },
                },
                ...(syncStatus
                  ? [
                      {
                        operation_id: "story-sync",
                        action: "sync" as const,
                        source: "kernel" as const,
                        status: syncStatus,
                        packages: {},
                        logs: {
                          environment:
                            "Reading notebook manifest\nResolving dependencies\nChecking Python version\n",
                        },
                      },
                    ]
                  : []),
              ]
            : [],
        },
      },
    }));
    const preparingEnvironment =
      props.backend &&
      (props.phase === "preparing" || props.phase === "failed");
    const getLogs2 = () => {
      if (preparingEnvironment) {
        return "";
      }
      if (props.backend) {
        return "Launching kernel process\nWaiting for kernel connection\n";
      }
      return "Launching kernel process\nConnecting to Python runtime\nWaiting for kernel connection\n";
    };
    state.set(startupProgressAtom, {
      phase: preparingEnvironment ? "preparing-environment" : "starting-kernel",
      logs: getLogs2(),
      log_mode: "replace",
    });
    if (props.existingCells) {
      const actions = createNotebookActions((action) =>
        state.set(notebookAtom, (value) => notebookReducer(value, action)),
      );
      actions.createNewCell({
        cellId: "__end__",
        before: false,
        code: 'import polars as pl\n\ntrips = pl.read_csv("bike_trips.csv")\ntrips.head()',
        autoFocus: false,
      });
    }
    state.set(requestClientAtom, {
      ...createStaticRequests(),
      getSandbox: async () => ({
        backend: props.backend,
        manifest: currentManifest,
        filename: "bike_trips.py",
      }),
      getPackageList: async () => ({
        packages: [
          { name: "marimo", version: "0.24.2" },
          { name: "polars", version: "1.34.0" },
        ],
      }),
      getDependencyTree: async () => ({
        context: props.backend
          ? { kind: "sandbox", backend: props.backend }
          : { kind: "package-manager", name: "pip" },
        tree: {
          name: "<root>",
          version: null,
          tags: [],
          dependencies: [
            { name: "marimo", version: "0.24.2", tags: [], dependencies: [] },
            { name: "polars", version: "1.34.0", tags: [], dependencies: [] },
          ],
        },
      }),
      updateManifest: async ({ contents }) => {
        if (props.saveResult === "stale") {
          throw new HTTPError(
            409,
            "The manifest changed on disk. Reopen it before saving.",
          );
        }
        currentManifest = contents;
        return {
          backend: props.backend,
          manifest: currentManifest,
          filename: "bike_trips.py",
        };
      },
      syncSandbox: async () => {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        if (props.saveResult === "failure") {
          return {
            success: false,
            error:
              "Failed to download rich from https://pypi.org/simple/rich/\n  Request failed after 3 retries: connection timed out",
            restartRequired: false,
            reconnect: false,
          };
        }
        state.set(connectionAtom, { state: WebSocketState.OPEN });
        state.set(kernelStartupErrorAtom, null);
        return {
          success: true,
          error: null,
          restartRequired: false,
          reconnect: false,
        };
      },
    });
    return state;
  });
  const appConfig = AppConfigSchema.parse({ width: "full" });
  const reconnect = async () => {
    store.set(connectionAtom, { state: WebSocketState.OPEN });
  };
  useEffect(() => {
    if (!props.interactive) {
      return;
    }
    const appendPreparation = (line: string) =>
      store.set(alertAtom, (value) => ({
        ...value,
        environments: {
          ...value.environments,
          kernel: {
            ...value.environments.kernel,
            operations: value.environments.kernel.operations.map(
              (operation) => ({
                ...operation,
                logs: { environment: operation.logs.environment + line },
              }),
            ),
          },
        },
      }));
    const timers = [
      setTimeout(() => appendPreparation("Installed 24 packages\n"), 1500),
      setTimeout(() => appendPreparation("Environment prepared\n"), 2500),
      setTimeout(() => {
        store.set(startupProgressAtom, {
          phase: "starting-kernel",
          logs: "Launching kernel process\nWaiting for kernel connection\n",
          log_mode: "replace",
        });
        store.set(connectionAtom, {
          state: WebSocketState.CONNECTING,
          phase: "starting-kernel",
        });
      }, 3500),
      setTimeout(
        () => store.set(connectionAtom, { state: WebSocketState.OPEN }),
        5500,
      ),
    ];
    return () => timers.forEach(clearTimeout);
  }, [props.interactive, store]);
  const getSurfaceDescription = () => {
    if (props.surface === "packages") {
      return "Packages sidebar.";
    }
    if (props.surface === "manifest") {
      return "Sandbox manifest editor.";
    }
    if (props.existingCells) {
      return "Notebook with existing cells: inline status opens Packages for stages and logs.";
    }
    return "Empty notebook: startup stages appear in the notebook until the kernel connects.";
  };
  return (
    <Provider store={store}>
      <SandboxController onReconnect={reconnect} />
      {props.surface === "manifest" && <OpenManifest />}
      <header className="mb-4 max-w-2xl space-y-1">
        <h1 className="text-base font-medium">
          {props.backend
            ? `${props.backend} sandbox environment`
            : "Existing Python environment"}
        </h1>
        <p className="text-sm text-muted-foreground">
          {props.backend
            ? "marimo prepares this notebook’s isolated environment, then starts its kernel. The button keeps the sandbox name while its status dot and details change."
            : "Python is already available, so only the kernel needs to connect. The button stays labeled Runtime; there is no sandbox preparation stage."}
        </p>
        <p className="text-xs text-muted-foreground">
          {getSurfaceDescription()}
        </p>
      </header>
      {props.manual && <LifecycleControls backend={props.backend} />}
      <RuntimePreview
        props={props}
        appConfig={appConfig}
        reconnect={reconnect}
      />
    </Provider>
  );
}

export const runtimeStoryMeta = {
  component: RuntimeStory,
  parameters: { layout: "centered" },
  args: {
    surface: "notebook",
    phase: "preparing",
    existingCells: true,
    backend: "uv",
    saveResult: "success",
    theme: "light",
    interactive: false,
    manual: false,
    detailsOpen: false,
  },
  render: (args, context) => (
    <RuntimeStory
      key={JSON.stringify([args, context.globals.theme])}
      {...args}
      theme={context.globals.theme === "dark" ? "dark" : "light"}
    />
  ),
} satisfies Meta<typeof RuntimeStory>;
