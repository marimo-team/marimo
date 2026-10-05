/* Copyright 2026 Marimo. All rights reserved. */
// @vitest-environment jsdom
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { Provider } from "jotai";
import { beforeEach, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { AppConfigSchema } from "@/core/config/config-schema";
import { ConnectionNotice } from "@/components/editor/alerts/connection-notice";
import { TooltipProvider } from "@/components/ui/tooltip";
import { kernelStartupErrorAtom } from "@/core/errors/state";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import {
  sandboxActionsAtom,
  sandboxAtom,
  sandboxSyncAtom,
} from "@/core/packages/sandbox-state";
import { filenameAtom } from "@/core/saving/file-state";
import { store } from "@/core/state/jotai";
import { WebSocketClosedReason, WebSocketState } from "@/core/websocket/types";
import { chromeAtom } from "../../state";
import PackagesPanel from "../packages-panel";
import { PanelSectionProvider } from "../panel-context";
import { SandboxController } from "../sandbox-controller";

vi.mock("@/plugins/impl/code/LazyAnyLanguageCodeMirror", () => ({
  LazyAnyLanguageCodeMirror: ({
    value,
    onChange,
    editable,
  }: {
    value: string;
    onChange: (value: string) => void;
    editable: boolean;
  }) => (
    <textarea
      aria-label="Notebook manifest"
      value={value}
      readOnly={!editable}
      onChange={(event) => onChange(event.target.value)}
    />
  ),
}));

const manifest =
  'dependencies = ["numpy==0.0.0"]\n\n[tool.custom]\nlabel = "experiment"\n';
const failed = {
  state: WebSocketState.CLOSED,
  code: WebSocketClosedReason.KERNEL_STARTUP_ERROR,
  phase: "preparing-environment",
  reason: "Kernel startup failed",
} as const;
beforeEach(() => {
  store.set(sandboxAtom, { backend: "uv", manifest, filename: "notebook.py" });
  store.set(sandboxSyncAtom, { kind: "succeeded" });
  store.set(sandboxActionsAtom, null);
  store.set(connectionAtom, failed);
  store.set(kernelStartupErrorAtom, "resolver output\n  no solution");
  store.set(filenameAtom, "notebook.py");
  store.set(chromeAtom, {
    selectedPanel: "packages",
    isSidebarOpen: false,
    isDeveloperPanelOpen: false,
    selectedDeveloperPanelTab: "errors",
  });
});
function mount(
  client: ReturnType<typeof MockRequestClient.create>,
  reconnect = vi.fn(async () => {}),
) {
  store.set(requestClientAtom, client);
  return render(
    <Provider store={store}>
      <TooltipProvider>
        <SandboxController onReconnect={reconnect} />
        <ConnectionNotice
          appConfig={AppConfigSchema.parse({})}
          onRetry={reconnect}
        />
        <PanelSectionProvider value="sidebar">
          <PackagesPanel />
        </PanelSectionProvider>
      </TooltipProvider>
    </Provider>,
  );
}
function requests() {
  return MockRequestClient.create({
    getSandbox: vi.fn(async () => ({
      backend: "uv",
      manifest,
      filename: "notebook.py",
    })),
    updateManifest: vi.fn(async ({ contents }) => ({
      backend: "uv",
      manifest: contents,
      filename: "notebook.py",
    })),
    syncSandbox: vi.fn(async () => ({ success: true, reconnect: true })),
  });
}

it("keeps a whole-manifest repair open through failure and closes only after sync succeeds", async () => {
  const client = requests();
  const { promise: saved, resolve: finishSave } = Promise.withResolvers<void>();
  vi.mocked(client.updateManifest).mockImplementation(async ({ contents }) => {
    await saved;
    return { backend: "uv", manifest: contents, filename: "notebook.py" };
  });
  const reconnect = vi.fn(async () => {
    store.set(kernelStartupErrorAtom, null);
    store.set(connectionAtom, {
      state: WebSocketState.CONNECTING,
      phase: "preparing-environment",
    });
  });
  mount(client, reconnect);
  fireEvent.click(await screen.findByRole("button", { name: "Open Packages" }));
  expect(store.get(chromeAtom).isSidebarOpen).toBe(true);
  expect(screen.getByLabelText("Error details")).toHaveTextContent(
    "resolver output",
  );
  fireEvent.click(screen.getByRole("button", { name: "Edit manifest…" }));
  const editor = await screen.findByRole("textbox", {
    name: "Notebook manifest",
  });
  const replacement =
    '# A completely different manifest\n[tool.custom]\nlabel = "updated"\n';
  fireEvent.change(editor, { target: { value: replacement } });
  fireEvent.click(screen.getByRole("button", { name: "Save & sync" }));
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(reconnect).not.toHaveBeenCalled();
  await act(async () => finishSave());
  await waitFor(() => expect(reconnect).toHaveBeenCalledTimes(1));
  expect(client.updateManifest).toHaveBeenCalledWith({
    fileKey: "notebook.py",
    previous: manifest,
    contents: replacement,
  });
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  act(() => {
    store.set(connectionAtom, failed);
    store.set(kernelStartupErrorAtom, "another resolver failure");
  });
  const dialog = within(screen.getByRole("dialog"));
  expect(await dialog.findByLabelText("Error details")).toHaveTextContent(
    "another resolver failure",
  );
  expect(
    dialog.getByRole("textbox", { name: "Notebook manifest" }),
  ).toHaveValue(replacement);
  await waitFor(() =>
    expect(dialog.getByRole("button", { name: "Sync" })).toBeEnabled(),
  );
  fireEvent.click(dialog.getByRole("button", { name: "Sync" }));
  await waitFor(() => expect(reconnect).toHaveBeenCalledTimes(2));
  act(() => store.set(connectionAtom, { state: WebSocketState.OPEN }));
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
});
