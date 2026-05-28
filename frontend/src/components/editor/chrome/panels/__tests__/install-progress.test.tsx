/* Copyright 2026 Marimo. All rights reserved. */

import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PackageInstallationStatus } from "@/core/kernel/messages";

const clearPackageAlert = vi.fn();

interface InstallingAlert {
  id: string;
  kind: "installing";
  packages: PackageInstallationStatus;
}

let alertState: {
  packageAlert: InstallingAlert | null;
  packageLogs: Record<string, string>;
} = { packageAlert: null, packageLogs: {} };

vi.mock("@/core/alerts/state", async (importActual) => {
  const actual = await importActual<object>();
  return {
    ...actual,
    useAlerts: () => alertState,
    useAlertActions: () => ({ clearPackageAlert }),
  };
});

// Light stand-ins for the heavy package-alert exports.
vi.mock("@/components/editor/package-alert", () => ({
  getInstallationStatusElements: (packages: PackageInstallationStatus) => {
    const statuses = new Set(Object.values(packages));
    const status =
      statuses.has("queued") || statuses.has("installing")
        ? "installing"
        : statuses.has("failed")
          ? "failed"
          : "installed";
    return {
      status,
      title:
        status === "installing"
          ? "Installing packages"
          : status === "failed"
            ? "Some packages failed to install"
            : "All packages installed!",
      titleIcon: <span data-testid="title-icon" />,
      description: "",
    };
  },
  ProgressIcon: ({ status }: { status: string }) => (
    <span data-testid={`progress-${status}`} />
  ),
  StreamingLogsViewer: ({
    packageLogs,
  }: {
    packageLogs: Record<string, string>;
  }) => <pre data-testid="logs">{JSON.stringify(packageLogs)}</pre>,
}));

const { InlineInstallProgress } = await import("../install-progress");

describe("InlineInstallProgress", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    alertState = { packageAlert: null, packageLogs: {} };
  });

  it("renders nothing when there is no installing alert", () => {
    const { container } = render(<InlineInstallProgress />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a collapsed summary while installing and expands on click", () => {
    alertState = {
      packageAlert: {
        id: "a1",
        kind: "installing",
        packages: { httpx: "installing" },
      },
      packageLogs: { httpx: "Resolved 394 packages\n" },
    };

    render(<InlineInstallProgress />);
    expect(screen.getByText("Installing packages")).toBeInTheDocument();
    // Collapsed: per-package list and logs are hidden.
    expect(screen.queryByTestId("progress-installing")).not.toBeInTheDocument();
    expect(screen.queryByTestId("logs")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Installing packages"));
    expect(screen.getByTestId("progress-installing")).toBeInTheDocument();
    expect(screen.getByTestId("logs")).toHaveTextContent(
      "Resolved 394 packages",
    );
  });

  it("auto-expands on failure to surface the error", () => {
    alertState = {
      packageAlert: {
        id: "a2",
        kind: "installing",
        packages: { httpx: "failed" },
      },
      packageLogs: { httpx: "ERROR: could not resolve\n" },
    };

    render(<InlineInstallProgress />);
    // Expanded without any click because the install failed.
    expect(screen.getByTestId("progress-failed")).toBeInTheDocument();
    expect(screen.getByTestId("logs")).toHaveTextContent(
      "ERROR: could not resolve",
    );
  });

  it("dismisses the alert", () => {
    alertState = {
      packageAlert: {
        id: "a3",
        kind: "installing",
        packages: { httpx: "installing" },
      },
      packageLogs: {},
    };

    render(<InlineInstallProgress />);
    fireEvent.click(screen.getByTestId("dismiss-install-progress-button"));
    expect(clearPackageAlert).toHaveBeenCalledWith("a3");
  });
});
