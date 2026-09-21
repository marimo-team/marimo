/* Copyright 2026 Marimo. All rights reserved. */
import type { Meta, StoryObj } from "@storybook/react-vite";
import { createStore, Provider, useAtomValue } from "jotai";
import { useEffect, useRef, useState } from "react";
import { ConnectionNotice } from "@/components/editor/alerts/connection-notice";
import PackagesPanel from "@/components/editor/chrome/panels/packages-panel";
import { SandboxController } from "@/components/editor/chrome/panels/sandbox-controller";
import { chromeAtom } from "@/components/editor/chrome/state";
import { Cell } from "@/components/editor/notebook-cell";
import { VerticalLayoutWrapper } from "@/components/editor/renderers/vertical-layout/vertical-layout-wrapper";
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
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import { createStaticRequests } from "@/core/network/requests-static";
import {
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "@/core/packages/sandbox-state";
import { filenameAtom } from "@/core/saving/file-state";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
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

interface Props {
  surface: "notebook" | "packages" | "manifest";
  phase:
    | "preparing"
    | "starting"
    | "failed"
    | "ready"
    | "syncing"
    | "sync-failed";
  existingCells: boolean;
  backend: "uv" | "pixi";
  saveResult: "success" | "failure" | "stale";
  theme: "light" | "dark";
  interactive: boolean;
}

function SandboxPreview({
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
          <div className="px-4 py-3 border-b text-sm">Packages</div>
          <PackagesPanel />
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

function SandboxStory(props: Props) {
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
      isSidebarOpen: props.surface !== "notebook",
      isDeveloperPanelOpen: false,
      selectedDeveloperPanelTab: "errors",
    });
    state.set(
      connectionAtom,
      props.phase === "preparing" || props.phase === "starting"
        ? {
            state: WebSocketState.CONNECTING,
            phase:
              props.phase === "preparing"
                ? "preparing-environment"
                : "starting-kernel",
          }
        : props.phase === "failed"
          ? {
              state: WebSocketState.CLOSED,
              code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
              reason: "Kernel startup failed",
              phase: "preparing-environment",
            }
          : { state: WebSocketState.OPEN },
    );
    state.set(
      kernelStartupErrorAtom,
      props.phase === "failed" ? resolutionError : null,
    );
    state.set(sandboxSyncAtom, {
      pending: props.phase === "syncing",
      error: props.phase === "sync-failed" ? resolutionError : null,
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
      getDependencyTree: async () => ({
        context: { kind: "sandbox", backend: props.backend },
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
    const timers = [
      setTimeout(
        () =>
          store.set(connectionAtom, {
            state: WebSocketState.CONNECTING,
            phase: "starting-kernel",
          }),
        3500,
      ),
      setTimeout(
        () => store.set(connectionAtom, { state: WebSocketState.OPEN }),
        5500,
      ),
    ];
    return () => timers.forEach(clearTimeout);
  }, [props.interactive, store]);
  return (
    <Provider store={store}>
      <SandboxController onReconnect={reconnect} />
      {props.surface === "manifest" && <OpenManifest />}
      <SandboxPreview
        props={props}
        appConfig={appConfig}
        reconnect={reconnect}
      />
    </Provider>
  );
}

const meta = {
  title: "Sandbox/States",
  component: SandboxStory,
  parameters: { layout: "centered" },
  args: {
    surface: "notebook",
    phase: "preparing",
    existingCells: true,
    backend: "uv",
    saveResult: "success",
    theme: "light",
    interactive: false,
  },
  render: (args, context) => (
    <SandboxStory
      key={JSON.stringify([args, context.globals.theme])}
      {...args}
      theme={context.globals.theme === "dark" ? "dark" : "light"}
    />
  ),
} satisfies Meta<typeof SandboxStory>;
export default meta;
type Story = StoryObj<typeof meta>;

export const ExistingNotebookPreparing: Story = {
  name: "Startup notice / preparing",
};
export const EmptyNotebookPreparing: Story = {
  name: "Empty notebook / preparing",
  args: { existingCells: false },
};
export const StartingKernel: Story = {
  name: "Startup notice / starting kernel",
  args: { phase: "starting" },
};
export const StartupTransition: Story = {
  name: "Startup / completion transition",
  args: { interactive: true, backend: "pixi" },
};
export const EmptyStartupTransition: Story = {
  name: "Empty notebook / completion transition",
  args: { interactive: true, existingCells: false, backend: "pixi" },
};
export const ExistingNotebookFailed: Story = {
  name: "Startup notice / failed",
  args: { phase: "failed" },
};
export const EmptyNotebookFailed: Story = {
  name: "Empty notebook / failed",
  args: { phase: "failed", existingCells: false },
};
export const PackagesPreparing: Story = {
  name: "Setup details / preparing",
  args: { surface: "packages" },
};
export const PackagesFailed: Story = {
  name: "Setup details / failed",
  args: { surface: "packages", phase: "failed" },
};
export const PackagesReady: Story = {
  name: "Status row / ready",
  args: { surface: "packages", phase: "ready" },
};
export const PackagesSyncing: Story = {
  name: "Status row / syncing",
  args: { surface: "packages", phase: "syncing" },
};
export const PackagesSyncFailed: Story = {
  name: "Setup details / sync failed",
  args: { surface: "packages", phase: "sync-failed" },
};
export const PixiPackagesReady: Story = {
  name: "Status row / pixi",
  args: { surface: "packages", phase: "ready", backend: "pixi" },
};
export const ManifestEditor: Story = {
  name: "Manifest / edit",
  args: { surface: "manifest", phase: "failed" },
};
export const ManifestSyncFails: Story = {
  name: "Manifest / failed save",
  args: { surface: "manifest", phase: "failed", saveResult: "failure" },
};
export const ManifestChangedOnDisk: Story = {
  name: "Manifest / changed on disk",
  args: { surface: "manifest", phase: "failed", saveResult: "stale" },
};
