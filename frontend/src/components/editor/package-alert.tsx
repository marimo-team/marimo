/* Copyright 2024 Marimo. All rights reserved. */

import { cn } from "@/utils/cn";
import { RuntimeState } from "@/core/kernel/RuntimeState";
import { sendInstallMissingPackages } from "@/core/network/requests";
import {
  useAlerts,
  useAlertActions,
  MissingPackageAlert,
  InstallingPackageAlert,
  isMissingPackageAlert,
  isInstallingPackageAlert,
} from "@/core/alerts/state";
import { Banner } from "@/plugins/impl/common/error-banner";
import {
  PackageXIcon,
  BoxIcon,
  CheckIcon,
  DownloadCloudIcon,
  PackageCheckIcon,
  XIcon,
} from "lucide-react";
import React from "react";
import { Button } from "../ui/button";
import { PackageInstallationStatus } from "@/core/kernel/messages";
import { logNever } from "@/utils/assertNever";
import { useUserConfig } from "@/core/config/config";

export const PackageAlert: React.FC = (props) => {
  const { packageAlert } = useAlerts();
  const { addPackageAlert, clearPackageAlert } = useAlertActions();
  const [userConfig] = useUserConfig();

  if (packageAlert === null) {
    return null;
  }

  if (isMissingPackageAlert(packageAlert)) {
    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200] opacity-95">
        <Banner
          kind="danger"
          className="flex flex-col rounded py-3 px-5 animate-in slide-in-from-left"
        >
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              <PackageXIcon className="w-5 h-5 inline-block mr-2" />
              Missing packages
            </span>
            <Button
              variant="text"
              data-testid="remove-banner-button"
              size="icon"
              onClick={() => clearPackageAlert(packageAlert.id)}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div className="flex flex-col gap-4 justify-between items-start text-muted-foreground text-base">
            <div>
              <p>The following packages were not found:</p>
              <ul className="list-disc ml-4 mt-1">
                {packageAlert.packages.map((pkg, index) => (
                  <li
                    className="flex items-center gap-1 font-mono text-sm"
                    key={index}
                  >
                    <BoxIcon size="1rem" />
                    {pkg}
                  </li>
                ))}
              </ul>
            </div>
            <div className="ml-auto">
              {packageAlert.isolated ? (
                <InstallPackagesButton
                  packages={packageAlert.packages}
                  manager={userConfig.package_management.manager}
                  addPackageAlert={addPackageAlert}
                />
              ) : (
                <p>
                  If you set up a{" "}
                  <a
                    href="https://docs.python.org/3/tutorial/venv.html#creating-virtual-environments"
                    className="text-accent-foreground hover:underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    virtual environment
                  </a>
                  , marimo can install these packages for you.
                </p>
              )}
            </div>
          </div>
        </Banner>
      </div>
    );
  } else if (isInstallingPackageAlert(packageAlert)) {
    const { status, title, titleIcon, description } =
      getInstallationStatusElements(packageAlert.packages);
    if (status === "installed") {
      setTimeout(() => clearPackageAlert(packageAlert.id), 10_000);
    }

    return (
      <div className="flex flex-col gap-4 mb-5 fixed top-5 left-5 w-[400px] z-[200] opacity-95">
        <Banner
          kind={status === "failed" ? "danger" : "info"}
          className="flex flex-col rounded pt-3 pb-4 px-5"
        >
          <div className="flex justify-between">
            <span className="font-bold text-lg flex items-center mb-2">
              {titleIcon}
              {title}
            </span>
            <Button
              variant="text"
              data-testid="remove-banner-button"
              size="icon"
              onClick={() => clearPackageAlert(packageAlert.id)}
            >
              <XIcon className="w-5 h-5" />
            </Button>
          </div>
          <div
            className={cn(
              "flex flex-col gap-4 justify-between items-start text-muted-foreground text-base",
              status === "installed" && "text-accent-foreground",
            )}
          >
            <div>
              <p>{description}</p>
              <ul className="list-disc ml-4 mt-1">
                {Object.entries(packageAlert.packages).map(
                  ([pkg, st], index) => (
                    <li
                      className={cn(
                        "flex items-center gap-1 font-mono text-sm",
                        st === "installing" && "font-semibold",
                        st === "failed" && "text-destructive",
                        st === "installed" && "text-accent-foreground",
                        st === "installed" &&
                          status === "failed" &&
                          "text-muted-foreground",
                      )}
                      key={index}
                    >
                      <ProgressIcon status={st} />
                      {pkg}
                    </li>
                  ),
                )}
              </ul>
            </div>
          </div>
        </Banner>
      </div>
    );
  } else {
    logNever(packageAlert);
    return null;
  }
};

function getInstallationStatusElements(packages: PackageInstallationStatus) {
  const statuses = new Set(Object.values(packages));
  const status =
    statuses.has("queued") || statuses.has("installing")
      ? "installing"
      : statuses.has("failed")
        ? "failed"
        : "installed";

  if (status === "installing") {
    return {
      status: "installing",
      title: "Installing packages",
      titleIcon: <DownloadCloudIcon className="w-5 h-5 inline-block mr-2" />,
      description: "Installing packages:",
    };
  } else if (status === "installed") {
    return {
      status: "installed",
      title: "All packages installed!",
      titleIcon: <PackageCheckIcon className="w-5 h-5 inline-block mr-2" />,
      description: "Installed packages:",
    };
  } else {
    return {
      status: "failed",
      title: "Some packages failed to install",
      titleIcon: <PackageXIcon className="w-5 h-5 inline-block mr-2" />,
      description: "See terminal for error logs.",
    };
  }
}

const ProgressIcon = ({
  status,
}: {
  status: PackageInstallationStatus[string];
}) => {
  switch (status) {
    case "queued":
      return <BoxIcon size="1rem" />;
    case "installing":
      return <DownloadCloudIcon size="1rem" />;
    case "installed":
      return <CheckIcon size="1rem" />;
    case "failed":
      return <XIcon size="1rem" />;
    default:
      logNever(status);
      return null;
  }
};

async function installPackages(
  packages: string[],
  manager: "pip" | "uv" | "rye",
  addPackageAlert: (
    alert: MissingPackageAlert | InstallingPackageAlert,
  ) => void,
) {
  const packageStatus = Object.fromEntries(
    packages.map((pkg) => [pkg, "queued"]),
  ) as PackageInstallationStatus;
  addPackageAlert({
    kind: "installing",
    packages: packageStatus,
  });
  RuntimeState.INSTANCE.registerRunStart();
  await sendInstallMissingPackages({ manager: manager });
}

const InstallPackagesButton = ({
  packages,
  manager,
  addPackageAlert,
}: {
  packages: string[];
  manager: "pip" | "uv" | "rye";
  addPackageAlert: (
    alert: MissingPackageAlert | InstallingPackageAlert,
  ) => void;
}) => {
  return (
    <Button
      variant="outline"
      data-testid="install-packages-button"
      size="sm"
      onClick={() => installPackages(packages, manager, addPackageAlert)}
    >
      <DownloadCloudIcon className="w-4 h-4 mr-2" />
      <span className="font-semibold">Install with {manager}</span>
    </Button>
  );
};
