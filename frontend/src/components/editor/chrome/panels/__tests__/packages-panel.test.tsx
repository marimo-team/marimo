/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { Provider } from "jotai";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { requestClientAtom } from "@/core/network/requests";
import type {
  DependencyTreeNode,
  DependencyTreeResponse,
} from "@/core/network/types";
import { store } from "@/core/state/jotai";
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
  const getPackageList = vi.fn().mockResolvedValue({ packages: [] });
  store.set(
    requestClientAtom,
    MockRequestClient.create({
      getPackageList,
      getDependencyTree: vi.fn().mockResolvedValue({ tree, context }),
    }),
  );

  return {
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
