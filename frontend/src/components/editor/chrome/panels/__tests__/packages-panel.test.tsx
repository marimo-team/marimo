/* Copyright 2026 Marimo. All rights reserved. */

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { connectionAtom } from "@/core/network/connection";
import { requestClientAtom } from "@/core/network/requests";
import type {
  DependencyTreeNode,
  DependencyTreeResponse,
} from "@/core/network/types";
import { withPackageInvalidation } from "@/core/packages/package-data";
import { useInstallPackages } from "@/core/packages/useInstallPackage";
import { sandboxAtom, sandboxSyncAtom } from "@/core/packages/sandbox-state";
import { store } from "@/core/state/jotai";
import { WebSocketState } from "@/core/websocket/types";
import PackagesPanel from "../packages-panel";

const { openSettings } = vi.hoisted(() => ({
  openSettings: vi.fn(),
}));

vi.mock("@/components/app-config/state", () => ({
  useOpenSettingsToTab: () => ({ handleClick: openSettings }),
}));

const emptyTree: DependencyTreeNode = {
  name: "<root>",
  version: null,
  tags: [],
  dependencies: [],
};

const populatedTree: DependencyTreeNode = {
  ...emptyTree,
  dependencies: [
    {
      name: "polars",
      version: "1.44.1",
      tags: [],
      dependencies: [
        {
          name: "numpy",
          version: "2.5.2",
          tags: [{ kind: "dedupe", value: "true" }],
          dependencies: [],
        },
      ],
    },
  ],
};

function renderPanel(
  context: DependencyTreeResponse["context"],
  tree: DependencyTreeNode = emptyTree,
) {
  store.set(
    sandboxAtom,
    context.kind === "sandbox"
      ? { backend: context.backend, manifest: "", filename: "notebook.py" }
      : null,
  );
  store.set(sandboxSyncAtom, { pending: false, error: null });
  const getPackageList = vi.fn().mockResolvedValue({ packages: [] });
  const client = MockRequestClient.create({
    getPackageList,
    getDependencyTree: vi.fn().mockResolvedValue({ tree, context }),
  });
  store.set(requestClientAtom, client);

  return {
    client,
    getPackageList,
    ...render(
      <Provider store={store}>
        <TooltipProvider>
          <PackagesPanel />
        </TooltipProvider>
      </Provider>,
    ),
  };
}

describe("PackagesPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each(["pixi", "uv"] as const)(
    "shows the effective %s sandbox backend as a fixed context",
    async (backend) => {
      const { getPackageList } = renderPanel({ kind: "sandbox", backend });

      expect(
        await screen.findByPlaceholderText(
          `Add packages to ${backend} sandbox...`,
        ),
      ).toBeInTheDocument();
      expect(screen.getByText(`${backend} sandbox`)).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Change package manager" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "List" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Tree" }),
      ).not.toBeInTheDocument();
      expect(getPackageList).not.toHaveBeenCalled();
    },
  );

  it("explains the filtered empty state for a Pixi sandbox", async () => {
    renderPanel({ kind: "sandbox", backend: "pixi" });

    expect(await screen.findByText("No PyPI dependencies")).toBeInTheDocument();
    expect(
      screen.getByText("Conda dependencies are not shown in this panel."),
    ).toBeInTheDocument();
  });

  it("labels a dependency whose subtree was already displayed", async () => {
    renderPanel({ kind: "sandbox", backend: "pixi" }, populatedTree);

    fireEvent.click(await screen.findByRole("treeitem", { name: /polars/ }));

    expect(screen.getByText("already in tree")).toBeInTheDocument();
    expect(screen.queryByText("cycle")).not.toBeInTheDocument();
  });

  it("keeps the configured package manager changeable outside a sandbox", async () => {
    const { getPackageList } = renderPanel({
      kind: "package-manager",
      name: "pip",
    });

    expect(
      await screen.findByPlaceholderText("Install packages with pip..."),
    ).toBeInTheDocument();
    const changeManager = screen.getByRole("button", {
      name: "Change package manager",
    });

    fireEvent.click(changeManager);

    expect(openSettings).toHaveBeenCalledWith("packageManagementAndData");
    expect(screen.getByText("environment")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "List" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tree" })).toBeInTheDocument();
    expect(getPackageList).toHaveBeenCalledOnce();
  });
});

it("refreshes an open panel when a package is installed elsewhere, after installation succeeds", async () => {
  const { promise, resolve } = Promise.withResolvers<{ success: boolean }>();
  const client = MockRequestClient.create({
    addPackage: vi.fn(() => promise),
    getDependencyTree: vi
      .fn()
      .mockResolvedValueOnce({
        tree: emptyTree,
        context: { kind: "sandbox", backend: "uv" },
      })
      .mockResolvedValue({
        tree: populatedTree,
        context: { kind: "sandbox", backend: "uv" },
      }),
  });
  store.set(sandboxAtom, {
    backend: "uv",
    manifest: "",
    filename: "notebook.py",
  });
  store.set(sandboxSyncAtom, { pending: false, error: null });
  store.set(requestClientAtom, withPackageInvalidation(client));
  function InstallElsewhere() {
    const { handleInstallPackages } = useInstallPackages();
    return (
      <button onClick={() => handleInstallPackages(["polars"])}>
        Install from another panel
      </button>
    );
  }
  render(
    <Provider store={store}>
      <TooltipProvider>
        <PackagesPanel />
        <InstallElsewhere />
      </TooltipProvider>
    </Provider>,
  );
  await screen.findByPlaceholderText("Add packages to uv sandbox...");
  fireEvent.click(
    screen.getByRole("button", { name: "Install from another panel" }),
  );
  expect(client.getDependencyTree).toHaveBeenCalledTimes(1);
  await act(async () => resolve({ success: true }));
  await waitFor(() =>
    expect(client.getDependencyTree).toHaveBeenCalledTimes(2),
  );
  expect(await screen.findByText("polars")).toBeInTheDocument();
});

it("keeps packages and the install draft visible while blocking mutations during sync", async () => {
  store.set(connectionAtom, { state: WebSocketState.OPEN });
  renderPanel({ kind: "sandbox", backend: "pixi" }, populatedTree);
  await screen.findByRole("treeitem", { name: /polars/ });
  const input = screen.getByPlaceholderText("Add packages to pixi sandbox...");
  fireEvent.change(input, { target: { value: "altair" } });
  act(() => store.set(sandboxSyncAtom, { pending: true, error: null }));
  const row = screen.getByRole("treeitem", { name: /polars/ });
  expect(
    screen.getByPlaceholderText("Add packages to pixi sandbox..."),
  ).toBeDisabled();
  expect(within(row).getByRole("button", { name: "Remove" })).toBeDisabled();
  expect(
    screen.queryByRole("list", { name: "Notebook startup stages" }),
  ).not.toBeInTheDocument();
  act(() =>
    store.set(sandboxSyncAtom, {
      pending: false,
      error: "Could not resolve dependencies",
    }),
  );
  expect(screen.getByRole("treeitem", { name: /polars/ })).toBeInTheDocument();
  expect(screen.getByLabelText("Error details")).toHaveTextContent(
    "Could not resolve dependencies",
  );
  const restoredInput = screen.getByPlaceholderText(
    "Add packages to pixi sandbox...",
  );
  expect(restoredInput).toHaveValue("altair");
  expect(restoredInput).toBeEnabled();
});

it.each(["uv", "pixi", "list"] as const)(
  "allows upgrading marimo but not removing it in the %s view",
  async (view) => {
    const tree = {
      ...populatedTree,
      dependencies: [
        ...populatedTree.dependencies,
        { name: "marimo", version: "0.24.0", tags: [], dependencies: [] },
      ],
    };
    const { client, getPackageList } = renderPanel(
      view === "list"
        ? { kind: "package-manager", name: "pip" }
        : { kind: "sandbox", backend: view },
      tree,
    );
    getPackageList.mockResolvedValue({ packages: tree.dependencies });
    vi.mocked(client.addPackage).mockResolvedValue({ success: true });
    if (view === "list") {
      fireEvent.click(await screen.findByRole("button", { name: "List" }));
    }
    const role = view === "list" ? "row" : "treeitem";
    const marimo = within(await screen.findByRole(role, { name: /marimo/ }));
    expect(marimo.getByText(/0\.24\.0/)).toBeInTheDocument();
    expect(
      marimo.queryByRole("button", { name: "Remove" }),
    ).not.toBeInTheDocument();
    const polars = within(screen.getByRole(role, { name: /polars/ }));
    expect(polars.getByRole("button", { name: "Remove" })).toBeInTheDocument();
    fireEvent.click(marimo.getByRole("button", { name: "Upgrade" }));
    await waitFor(() =>
      expect(client.addPackage).toHaveBeenCalledWith({
        package: "marimo",
        upgrade: true,
        group: undefined,
      }),
    );
    expect(client.removePackage).not.toHaveBeenCalled();
  },
);
