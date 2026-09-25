/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { createStore, Provider } from "jotai";
import { expect, it, vi } from "vitest";
import { MockRequestClient } from "@/__mocks__/requests";
import { TooltipProvider } from "@/components/ui/tooltip";
import { alertAtom } from "@/core/alerts/state";
import {
  defaultUserConfig,
  type PackageManagerName,
} from "@/core/config/config-schema";
import { userConfigAtom } from "@/core/config/config";
import { requestClientAtom } from "@/core/network/requests";
import { sandboxAtom } from "@/core/packages/sandbox-state";
import { PackageAlert } from "../package-alert";

vi.mock("@/hooks/usePackageMetadata", () => ({
  usePackageMetadata: () => ({
    data: { versions: [], extras: [] },
    error: null,
    isPending: false,
  }),
}));

function mountPackageAlert({
  configuredManager,
  sandboxBackend,
  source = "kernel",
}: {
  configuredManager: PackageManagerName;
  sandboxBackend: "uv" | "pixi" | null;
  source?: "kernel" | "server";
}) {
  const store = createStore();
  const client = MockRequestClient.create();
  const config = defaultUserConfig();
  store.set(userConfigAtom, {
    ...config,
    package_management: { manager: configuredManager },
  });
  store.set(requestClientAtom, client);
  store.set(
    sandboxAtom,
    sandboxBackend
      ? {
          backend: sandboxBackend,
          manifest: "",
          filename: "notebook.py",
        }
      : null,
  );
  store.set(alertAtom, {
    ...store.get(alertAtom),
    packageAlert: {
      id: "missing-package",
      kind: "missing",
      packages: ["polars"],
      isolated: true,
      source,
    },
  });
  render(
    <Provider store={store}>
      <TooltipProvider>
        <PackageAlert />
      </TooltipProvider>
    </Provider>,
  );
  return client;
}

it.each(["uv", "pixi"] as const)(
  "shows the fixed %s manager for a sandbox",
  (sandboxBackend) => {
    const client = mountPackageAlert({
      configuredManager: sandboxBackend === "uv" ? "pixi" : "uv",
      sandboxBackend,
    });

    const managerSelect = screen.getByTestId("install-package-manager-select");
    expect(managerSelect).toHaveValue(sandboxBackend);
    expect(managerSelect).toBeDisabled();

    fireEvent.click(screen.getByTestId("install-packages-button"));
    expect(client.sendInstallMissingPackages).toHaveBeenCalledWith(
      expect.objectContaining({ manager: sandboxBackend }),
    );
  },
);

it("keeps the configured package manager selectable outside a sandbox", () => {
  mountPackageAlert({ configuredManager: "uv", sandboxBackend: null });

  const managerSelect = screen.getByTestId("install-package-manager-select");
  expect(managerSelect).toHaveValue("uv");
  expect(managerSelect).not.toBeDisabled();
});

it("does not offer a package manager for a server installation", () => {
  mountPackageAlert({
    configuredManager: "uv",
    sandboxBackend: "pixi",
    source: "server",
  });

  expect(
    screen.queryByTestId("install-package-manager-select"),
  ).not.toBeInTheDocument();
});
